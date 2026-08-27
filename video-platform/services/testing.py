"""外部 API 连通性测试引擎（内存任务，不入库）

职责：
- 4 类 vendor 测试：llm / t2i / i2v / tts
- 异步执行：submit 立即返回 task_id，前端轮询 status
- 结果仅存内存（LRU 上限 20），不写 scenes/assets 表
- 支持 settings 临时覆盖（前端未保存的表单值）

约定：
- 测试产物下载到 output/_test/{task_id}/，完成即留待预览（下次清理时删除）
- 每个 vendor 同时只允许一个任务运行（避免 GPU 争抢）
"""

import base64
import logging
import os
import shutil
import threading
import time
import uuid
from typing import Dict, List, Optional

from services.db import get_setting

logger = logging.getLogger(__name__)

# ============================================================
# 常量
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_ROOT = os.path.join(PROJECT_ROOT, "output", "_test")

VENDORS = ("llm", "t2i", "i2v", "tts")

# 单 vendor 超时（秒）；i2v 首次调用需加载模型，放宽到 300s
TEST_TIMEOUTS = {"llm": 60, "t2i": 90, "i2v": 300, "tts": 60}

MAX_TASKS = 20          # LRU 上限
GPU_MIN_FREE_MB = 2048   # 显存低于该值提示资源不足
TASK_TTL_SECONDS = 1800  # 结果保留 30 分钟

# 图生视频测试输入图（256x256 纯色 PNG，base64 内嵌，零外部依赖）
TEST_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAIAAADTED8xAAACAElEQVR42u3TQQ0AAAjEsNOHOuzhhjcaaFIFS5bqgbciAQYAA4AB"
    "wABgADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4AB"
    "wABgADAAGAAMAAYAA4ABMIAKGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABg"
    "ADAAGAAMAAYAA4ABwABgADAAGAAMAAYAA4ABwABgADAAGAAMAAbAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAY"
    "AAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAGUAEDgAHAAGAAMAAYAAwA"
    "BgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwABgADgAHAAGAAMAAYAAwA"
    "BgADgAHAABgADAAGAAOAAcAAYAAwABgADAAGAAOAAcAAYAAwABgADAAGAAOAAcAAYAAwABgADAAGAAOAAcAAYAAwABgADAAGAAOA"
    "AcAAYAAwABgADAAGAAOAAcAAYAAwAFwLdaIZfhN+i0UAAAAASUVORK5CYII="
)


# ============================================================
# 任务记录（内存 LRU）
# ============================================================
_TASKS: Dict[str, dict] = {}
_LOCK = threading.Lock()


def _new_record(vendor: str, task_id: str) -> dict:
    return {
        "task_id": task_id,
        "vendor": vendor,
        "status": "running",       # running | success | error
        "stage": "pending",        # pending | system_stats | generate | fetch | done
        "elapsed_ms": 0,
        "detail": None,
        "response": None,
        "artifacts": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }


def _touch(record: dict) -> None:
    record["updated_at"] = time.time()


def _cleanup() -> None:
    """LRU + TTL 清理：超过 MAX_TASKS 删最旧；超过 TTL 删过期"""
    now = time.time()
    with _LOCK:
        expired = [k for k, v in _TASKS.items() if now - v["created_at"] > TASK_TTL_SECONDS]
        for k in expired:
            _TASKS.pop(k, None)
        if len(_TASKS) > MAX_TASKS:
            # 按创建时间升序删除多余
            ordered = sorted(_TASKS.items(), key=lambda kv: kv[1]["created_at"])
            for k, _ in ordered[: len(_TASKS) - MAX_TASKS]:
                _TASKS.pop(k, None)


def submit_test(vendor: str, overrides: Optional[dict] = None) -> str:
    """创建任务记录，返回 task_id（run_test 由 BackgroundTasks 异步执行）"""
    task_id = uuid.uuid4().hex[:16]
    with _LOCK:
        _TASKS[task_id] = _new_record(vendor, task_id)
        _TASKS[task_id]["overrides"] = overrides or {}
    _cleanup()
    return task_id


def get_test_status(task_id: str) -> Optional[dict]:
    """查询任务状态（脱敏：不返回 overrides）"""
    with _LOCK:
        rec = _TASKS.get(task_id)
        if not rec:
            return None
        return {
            "task_id": rec["task_id"],
            "vendor": rec["vendor"],
            "status": rec["status"],
            "stage": rec["stage"],
            "elapsed_ms": rec["elapsed_ms"],
            "detail": rec["detail"],
            "response": rec["response"],
            "artifacts": rec["artifacts"],
        }


def _finish_error(record: dict, detail: str) -> None:
    record["status"] = "error"
    record["stage"] = "error"
    record["detail"] = detail
    record["elapsed_ms"] = int((time.time() - record["created_at"]) * 1000)
    logger.warning(f"[TEST:{record['vendor']}] 失败: {detail}")


# ============================================================
# 4 类 vendor 测试执行
# ============================================================
def run_test(vendor: str, task_id: str) -> None:
    """执行测试并回写结果（后台线程）"""
    with _LOCK:
        record = _TASKS.get(task_id)
    if record is None:
        return

    try:
        if vendor == "llm":
            _run_llm(record)
        elif vendor == "t2i":
            _run_t2i(record)
        elif vendor == "i2v":
            _run_i2v(record)
        elif vendor == "tts":
            _run_tts(record)
    except Exception as e:
        _finish_error(record, f"{type(e).__name__}: {e}")
        return

    record["status"] = "success"
    record["stage"] = "done"
    record["elapsed_ms"] = int((time.time() - record["created_at"]) * 1000)
    logger.info(f"[TEST:{vendor}] 通过，耗时 {record['elapsed_ms']}ms")


def _merged_settings(record: dict) -> dict:
    """表单覆盖值优先，未提供字段用 settings 表兜底"""
    merged = dict(get_setting.__globals__ if False else {})
    from services.db import load_settings
    base = load_settings()
    base.update(record.get("overrides", {}))
    return base


def _artifacts_from_files(task_id: str, files: List[str]) -> List[dict]:
    """把下载产物转为 artifacts 描述（相对 URL 由前端拼接）"""
    arts = []
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            mtype = "image"
        elif ext in (".mp4", ".webm", ".mov"):
            mtype = "video"
        elif ext in (".wav", ".mp3", ".m4a", ".ogg"):
            mtype = "audio"
        else:
            mtype = "file"
        arts.append({
            "type": mtype,
            "filename": os.path.basename(fp),
            "size_bytes": os.path.getsize(fp) if os.path.exists(fp) else 0,
            "url": f"/api/settings/test/preview/{task_id}/{os.path.basename(fp)}",
        })
    return arts


def _run_llm(record: dict) -> None:
    """LLM 测试：OpenAI 兼容 /chat/completions，短文本对话"""
    from services.llm_client import LLMClient
    s = _merged_settings(record)
    if not s.get("llm_api_base"):
        raise RuntimeError("未配置 llm_api_base")
    if not s.get("llm_model"):
        raise RuntimeError("未配置 llm_model")

    client = LLMClient(
        api_base=s.get("llm_api_base"),
        api_key=s.get("llm_api_key"),
        model=s.get("llm_model"),
        timeout=TEST_TIMEOUTS["llm"],
    )
    record["stage"] = "generate"
    content = client.chat(
        messages=[{"role": "user", "content": "请只回复两个字：正常"}],
        temperature=0.0,
        max_tokens=20,
    )
    record["response"] = {
        "model": client.model,
        "content_preview": (content or "")[:120],
    }


def _check_system_stats(record: dict, client) -> dict:
    """第 1 步：/system_stats；显存不足给提示但仍继续（连通性已证明）"""
    record["stage"] = "system_stats"
    stats = client.get_system_stats()
    devices = stats.get("devices") or []
    gpu_name = devices[0].get("name", "unknown") if devices else "unknown"
    vram_free_mb = 0
    try:
        vram_free_mb = int(devices[0]["vram_free"] / 1024 / 1024) if devices else 0
    except Exception:
        pass
    record["response"] = {
        "gpu": gpu_name,
        "vram_free_mb": vram_free_mb,
        "comfyui_version": stats.get("system", {}).get("comfyui_version", "unknown"),
    }
    if vram_free_mb and vram_free_mb < GPU_MIN_FREE_MB:
        logger.warning(f"[TEST] 显存偏低: {vram_free_mb}MB < {GPU_MIN_FREE_MB}MB，生成可能较慢")
    return stats


def _run_t2i(record: dict) -> None:
    """文生图测试：system_stats → 极简 4 步 512x512 工作流 → 轮询 → 下载"""
    from services.comfyui_img import ComfyUIImgClient
    s = _merged_settings(record)
    if not s.get("t2i_url"):
        raise RuntimeError("未配置 t2i_url")

    client = ComfyUIImgClient(
        base_url=s.get("t2i_url"),
        token=s.get("t2i_token"),
        timeout=TEST_TIMEOUTS["t2i"],
        poll_interval=5,
    )
    _check_system_stats(record, client)

    task_dir = os.path.join(TEST_ROOT, record["task_id"])
    os.makedirs(task_dir, exist_ok=True)

    record["stage"] = "generate"
    wf = client.build_test_t2i_workflow(prompt="1dog", width=512, height=512)
    prompt_id = client.submit_workflow(wf)
    entry = client.poll_result(prompt_id, timeout=TEST_TIMEOUTS["t2i"])
    if not entry:
        raise RuntimeError("文生图任务未在预期时间内完成（可能排队或失败）")

    record["stage"] = "fetch"
    files = client.download_output(entry, task_dir)
    if not files:
        raise RuntimeError("文生图任务完成但未返回图片")
    record["artifacts"] = _artifacts_from_files(record["task_id"], files)


def _run_i2v(record: dict) -> None:
    """图生视频测试：system_stats → 内嵌测试图上传 → 1 秒 360x360 工作流 → 轮询 → 下载"""
    from services.comfyui_vid import ComfyUIVidClient
    s = _merged_settings(record)
    if not s.get("i2v_url"):
        raise RuntimeError("未配置 i2v_url")

    client = ComfyUIVidClient(
        base_url=s.get("i2v_url"),
        token=s.get("i2v_token"),
        timeout=TEST_TIMEOUTS["i2v"],
        poll_interval=5,
    )
    _check_system_stats(record, client)

    task_dir = os.path.join(TEST_ROOT, record["task_id"])
    os.makedirs(task_dir, exist_ok=True)

    # 第 2 步：写入内嵌测试图并上传
    record["stage"] = "generate"
    img_path = os.path.join(task_dir, "test_input.png")
    with open(img_path, "wb") as f:
        f.write(base64.b64decode(TEST_IMAGE_B64))

    upload_result = client.upload_image(img_path)
    image_name = upload_result.get("name", "test_input.png")
    logger.info(f"[TEST:i2v] 测试图上传完成: {image_name}")

    # 第 3 步：1 秒 / 16 帧 / 360x360 极简工作流
    wf = client.build_test_i2v_workflow(
        image_name, prompt="test video",
        width=360, height=360, length=16, fps=16,
    )
    prompt_id = client.submit_workflow(wf)
    entry = client.poll_result(prompt_id, timeout=TEST_TIMEOUTS["i2v"])
    if not entry:
        raise RuntimeError("图生视频任务未在预期时间内完成（首次调用需加载模型，可能较慢）")

    record["stage"] = "fetch"
    files = client.download_output(entry, task_dir)
    # 排除测试输入图本身
    files = [fp for fp in files if os.path.basename(fp) != "test_input.png"]
    if not files:
        raise RuntimeError("图生视频任务完成但未返回视频")
    record["artifacts"] = _artifacts_from_files(record["task_id"], files)


def _run_tts(record: dict) -> None:
    """语音合成测试：IndexTTS /gen_single 合成一句短文本"""
    from services.voice_actor import VoiceActor
    s = _merged_settings(record)
    if not s.get("tts_base_url"):
        raise RuntimeError("未配置 tts_base_url")

    task_dir = os.path.join(TEST_ROOT, record["task_id"])
    os.makedirs(task_dir, exist_ok=True)
    out_path = os.path.join(task_dir, "test_tts.wav")

    record["stage"] = "generate"
    actor = VoiceActor(
        base_url=s.get("tts_base_url"),
        username=s.get("tts_username"),
        password=s.get("tts_password"),
    )
    result_path = actor.self_test(output_path=out_path)

    if not os.path.exists(result_path) or os.path.getsize(result_path) < 1024:
        raise RuntimeError("语音合成返回文件缺失或过小")
    record["artifacts"] = _artifacts_from_files(record["task_id"], [result_path])
