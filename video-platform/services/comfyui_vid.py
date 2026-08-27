"""ComfyUI 图生视频客户端（V2.0 参数化）

构造函数支持显式传参（GenerationManager 按 config_snapshot 注入 base_url/token/timeout/poll_interval）；
参数为 None 时从 settings 表读取兜底（兼容 test/ 脚本直接 ComfyUIVidClient()）。
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


class ComfyUIVidClient:
    """ComfyUI 图生视频客户端"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
        poll_interval: Optional[int] = None,
        client_id: str = "video-platform",
        stop_check: Optional[Callable[[], None]] = None,
    ):
        self.base_url = (base_url or get_setting("i2v_url", "")).rstrip("/")
        self.token = token or get_setting("i2v_token", "")
        self.timeout = int(timeout or get_setting("i2v_timeout", "300") or 300)
        self.poll_interval = int(poll_interval or get_setting("i2v_poll_interval", "10") or 10)
        self.client_id = client_id
        self._stop_check = stop_check
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
        """中断 ComfyUI 当前正在执行的 prompt"""
        try:
            resp = self.session.post(f"{self.base_url}/interrupt", json={}, timeout=10)
            logger.info(f"ComfyUI(/interrupt) HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"ComfyUI interrupt 失败: {e}")

    def upload_image(self, image_path: str) -> dict:
        """上传图片到 ComfyUI（用于图生视频的输入图）"""
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"{self.base_url}/upload/image",
                headers={"Authorization": f"Bearer {self.token}"},
                files={"image": (os.path.basename(image_path), f, "image/png")},
                data={"type": "input"},
                timeout=30,
            )
        resp.raise_for_status()
        return resp.json()

    # ---- 工作流提交与轮询 ----

    def submit_workflow(self, workflow: dict) -> str:
        """提交工作流，返回 prompt_id"""
        payload = {"prompt": workflow, "client_id": self.client_id}
        resp = self.session.post(f"{self.base_url}/prompt", json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("prompt_id", "")

    def poll_result(self, prompt_id: str, timeout: Optional[int] = None, interval: Optional[int] = None) -> Optional[dict]:
        """轮询等待工作流完成。stop 触发则调 /interrupt 后抛 StopGeneration。"""
        timeout = int(timeout or self.timeout)
        interval = int(interval or self.poll_interval)
        start = time.time()
        while True:
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

    def build_i2v_workflow(
        self,
        image_name: str,
        prompt: str,
        width: int = 640,
        height: int = 368,
        length: int = 65,
        fps: int = 16,
        seed: Optional[int] = None,
    ) -> dict:
        """构建 Wan2.2 图生视频工作流"""
        seed1 = seed if seed is not None else random.randint(1, 2**31 - 1)
        seed2 = random.randint(1, 2**31 - 1)

        return {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "2": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "3": {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": ["1", 0],
                    "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                    "strength_model": 1,
                    "strength_clip": 1,
                },
            },
            "4": {
                "class_type": "LoraLoaderModelOnly",
                "inputs": {
                    "model": ["2", 0],
                    "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                    "strength_model": 1,
                    "strength_clip": 1,
                },
            },
            "5": {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": ["3", 0], "shift": 5},
            },
            "6": {
                "class_type": "ModelSamplingSD3",
                "inputs": {"model": ["4", 0], "shift": 5},
            },
            "7": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                    "type": "wan",
                    "device": "default",
                },
            },
            "8": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
            },
            "9": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["7", 0], "text": prompt},
            },
            "10": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["7", 0], "text": ""},
            },
            "11": {
                "class_type": "LoadImage",
                "inputs": {"image": image_name},
            },
            "12": {
                "class_type": "WanImageToVideo",
                "inputs": {
                    "positive": ["9", 0],
                    "negative": ["10", 0],
                    "vae": ["8", 0],
                    "start_image": ["11", 0],
                    "width": width,
                    "height": height,
                    "length": length,
                    "batch_size": 1,
                },
            },
            "13": {
                "class_type": "KSamplerAdvanced",
                "inputs": {
                    "model": ["5", 0],
                    "add_noise": "enable",
                    "noise_seed": seed1,
                    "steps": 4,
                    "cfg": 1,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "positive": ["12", 0],
                    "negative": ["12", 1],
                    "latent_image": ["12", 2],
                    "start_at_step": 0,
                    "end_at_step": 2,
                    "return_with_leftover_noise": "enable",
                },
            },
            "14": {
                "class_type": "KSamplerAdvanced",
                "inputs": {
                    "model": ["6", 0],
                    "add_noise": "disable",
                    "noise_seed": seed2,
                    "steps": 4,
                    "cfg": 1,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "positive": ["12", 0],
                    "negative": ["12", 1],
                    "latent_image": ["13", 0],
                    "start_at_step": 2,
                    "end_at_step": 4,
                    "return_with_leftover_noise": "disable",
                },
            },
            "15": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["14", 0], "vae": ["8", 0]},
            },
            "16": {
                "class_type": "CreateVideo",
                "inputs": {"images": ["15", 0], "fps": fps},
            },
            "17": {
                "class_type": "SaveVideo",
                "inputs": {
                    "video": ["16", 0],
                    "filename_prefix": "vid_",
                    "format": "mp4",
                    "codec": "h264",
                },
            },
        }

    def build_test_i2v_workflow(
        self,
        image_name: str,
        prompt: str = "test video",
        width: int = 360,
        height: int = 360,
        length: int = 16,
        fps: int = 16,
        seed: Optional[int] = None,
    ) -> dict:
        """测试专用图生视频工作流（复用生产 Wan2.2 lightx2v 节点，1 秒/16 帧极简版）"""
        return self.build_i2v_workflow(
            image_name, prompt, width=width, height=height, length=length, fps=fps, seed=seed
        )

    def generate_i2v(
        self, image_path: str, prompt: str,
        width: int = 640, height: int = 360,
        length: int = 65, fps: int = 16,
        seed: Optional[int] = None,
        output_dir: str = "./output",
    ) -> list:
        """图生视频：完整流程（上传+提交+轮询+下载），使用 self.timeout/self.poll_interval"""
        logger.info(f"上传图片: {image_path}")
        upload_result = self.upload_image(image_path)
        image_name = upload_result.get("name", os.path.basename(image_path))
        logger.info(f"上传完成: {image_name}")

        wf = self.build_i2v_workflow(image_name, prompt, width, height, length, fps, seed)
        prompt_id = self.submit_workflow(wf)
        logger.info(f"图生视频已提交: prompt_id={prompt_id}")

        entry = self.poll_result(prompt_id)
        if not entry:
            raise RuntimeError("图生视频超时或失败")

        return self.download_output(entry, output_dir)
