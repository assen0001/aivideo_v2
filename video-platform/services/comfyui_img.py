"""ComfyUI 文生图客户端（V2.0 参数化）

构造函数支持显式传参（GenerationManager 按 config_snapshot 注入 base_url/token/timeout/poll_interval）；
参数为 None 时从 settings 表读取兜底（兼容 test/ 脚本直接 ComfyUIImgClient()）。
"""

import json
import logging
import os
import random
import time
from typing import Callable, Optional
import requests

from services.db import get_setting
from services.stop_flag import StopGeneration

logger = logging.getLogger(__name__)


class ComfyUIImgClient:
    """ComfyUI 文生图客户端"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
        poll_interval: Optional[int] = None,
        client_id: str = "video-platform",
        stop_check: Optional[Callable[[], None]] = None,
    ):
        self.base_url = (base_url or get_setting("t2i_url", "")).rstrip("/")
        self.token = token or get_setting("t2i_token", "")
        self.timeout = int(timeout or get_setting("t2i_timeout", "300") or 300)
        self.poll_interval = int(poll_interval or get_setting("t2i_poll_interval", "5") or 5)
        self.client_id = client_id
        self._stop_check = stop_check  # 用户主动停止时的回调（None 表示不启用）
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })

    # ---- 基础 API ----

    def get_system_stats(self) -> dict:
        """获取系统状态"""
        resp = self.session.get(f"{self.base_url}/system_stats", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def free_memory(self):
        """释放显存"""
        try:
            self.session.post(f"{self.base_url}/free", json={"unload_models": True}, timeout=10)
        except Exception as e:
            logger.warning(f"释放显存失败: {e}")

    def interrupt(self) -> None:
        """中断 ComfyUI 当前正在执行的 prompt（/interrupt 立即终止推理）。"""
        try:
            resp = self.session.post(f"{self.base_url}/interrupt", json={}, timeout=10)
            logger.info(f"ComfyUI(/interrupt) HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"ComfyUI interrupt 失败: {e}")

    def clear_queue(self) -> None:
        """清空 ComfyUI 任务队列（/queue 清空剩余任务）。"""
        try:
            resp = self.session.post(f"{self.base_url}/queue", json={"clear": True}, timeout=10)
            logger.info(f"ComfyUI(/queue clear) HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"ComfyUI clear queue 失败: {e}")

    # ---- 工作流提交与轮询 ----

    def submit_workflow(self, workflow: dict) -> str:
        """提交工作流，返回 prompt_id"""
        payload = {"prompt": workflow, "client_id": self.client_id}
        resp = self.session.post(f"{self.base_url}/prompt", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("prompt_id", "")

    def poll_result(self, prompt_id: str, timeout: Optional[int] = None, interval: Optional[int] = None) -> Optional[dict]:
        """轮询等待工作流完成。每轮询间隔检查 stop_check；触发则调 /interrupt 后抛 StopGeneration。"""
        timeout = int(timeout or self.timeout)
        interval = int(interval or self.poll_interval)
        start = time.time()
        while True:
            # 停止检查：先抛 StopGeneration，由 GenerationManager.run 捕获 + 写库
            if self._stop_check is not None:
                try:
                    self._stop_check()
                except StopGeneration:
                    self.interrupt()
                    raise
            elapsed = time.time() - start
            if elapsed > timeout:
                logger.warning(f"轮询超时 ({int(elapsed)}s)")
                return None

            resp = self.session.get(
                f"{self.base_url}/history/{prompt_id}",
                timeout=30,
            )
            resp.raise_for_status()
            history = resp.json()

            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("completed", False):
                    logger.info(f"工作流完成，耗时 {int(elapsed)}s")
                    return entry
                elif status.get("status_str") == "error":
                    logger.error(f"工作流错误: {json.dumps(status, ensure_ascii=False)}")
                    return None

            time.sleep(interval)

        return None

    def download_output(self, entry: dict, output_dir: str) -> list:
        """下载工作流输出文件（图片/视频）"""
        os.makedirs(output_dir, exist_ok=True)
        saved = []

        outputs = entry.get("outputs", {})
        for node_id, node_output in outputs.items():
            for key in ("gifs", "videos"):
                if key in node_output:
                    for finfo in node_output[key]:
                        saved.extend(self._download_media(finfo, output_dir))

            if "images" in node_output:
                for img_info in node_output["images"]:
                    saved.extend(self._download_media(img_info, output_dir, is_image=True))

        return saved

    def _download_media(self, file_info: dict, output_dir: str, is_image: bool = False) -> list:
        filename = file_info["filename"]
        subfolder = file_info.get("subfolder", "")
        media_type = file_info.get("type", "output")

        url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={media_type}"
        resp = self.session.get(url, timeout=60)
        resp.raise_for_status()

        save_path = os.path.join(output_dir, filename)
        with open(save_path, "wb") as f:
            f.write(resp.content)

        size_str = f"{len(resp.content)/1024/1024:.1f} MB" if not is_image else f"{len(resp.content)/1024:.1f} KB"
        logger.info(f"下载: {save_path} ({size_str})")
        return [save_path]

    # ---- 专用工作流 ----

    def build_t2i_workflow(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 576,
        seed: Optional[int] = None,
    ) -> dict:
        """构建 z-image-turbo 文生图工作流"""
        actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)

        return {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "z_image_turbo_bf16.safetensors",
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "qwen_3_4b.safetensors",
                    "type": "lumina2",
                    "device": "default",
                },
            },
            "3": {
                "class_type": "ModelSamplingAuraFlow",
                "inputs": {"model": ["1", 0], "shift": 3},
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": prompt},
            },
            "5": {
                "class_type": "ConditioningZeroOut",
                "inputs": {"conditioning": ["4", 0]},
            },
            "6": {
                "class_type": "EmptySD3LatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["3", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["6", 0],
                    "seed": actual_seed,
                    "steps": 8,
                    "cfg": 1,
                    "sampler_name": "res_multistep",
                    "scheduler": "simple",
                    "denoise": 1,
                },
            },
            "8": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"},
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["7", 0], "vae": ["8", 0]},
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {"images": ["9", 0], "filename_prefix": "scene_"},
            },
        }

    def build_test_t2i_workflow(
        self,
        prompt: str = "1dog",
        width: int = 512,
        height: int = 512,
        seed: Optional[int] = None,
    ) -> dict:
        """测试专用极简文生图工作流（4 步，512x512，降低 GPU 耗时）

        与生产 build_t2i_workflow（8 步）隔离，仅用于配置页连通性测试。
        """
        actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)

        return {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "z_image_turbo_bf16.safetensors",
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "qwen_3_4b.safetensors",
                    "type": "lumina2",
                    "device": "default",
                },
            },
            "3": {
                "class_type": "ModelSamplingAuraFlow",
                "inputs": {"model": ["1", 0], "shift": 3},
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["2", 0], "text": prompt},
            },
            "5": {
                "class_type": "ConditioningZeroOut",
                "inputs": {"conditioning": ["4", 0]},
            },
            "6": {
                "class_type": "EmptySD3LatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["3", 0],
                    "positive": ["4", 0],
                    "negative": ["5", 0],
                    "latent_image": ["6", 0],
                    "seed": actual_seed,
                    "steps": 4,
                    "cfg": 1,
                    "sampler_name": "res_multistep",
                    "scheduler": "simple",
                    "denoise": 1,
                },
            },
            "8": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"},
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["7", 0], "vae": ["8", 0]},
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {"images": ["9", 0], "filename_prefix": "test_t2i_"},
            },
        }

    def generate_t2i(
        self, prompt: str, width: int = 1024, height: int = 576, seed: Optional[int] = None,
        output_dir: str = "./output",
    ) -> list:
        """文生图：完整流程（提交+轮询+下载），使用 self.timeout/self.poll_interval"""
        wf = self.build_t2i_workflow(prompt, width, height, seed)
        prompt_id = self.submit_workflow(wf)
        logger.info(f"文生图已提交: prompt_id={prompt_id}")

        entry = self.poll_result(prompt_id)
        if not entry:
            raise RuntimeError("文生图超时或失败")

        return self.download_output(entry, output_dir)
