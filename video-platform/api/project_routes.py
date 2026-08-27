"""项目模块路由（7 接口 + 单并发 + 快照 + 删除级联，P0）

接口：创建 / 生成 / 状态 / 详情 / 列表 / 删除 / 下载
"""

import json
import logging
import re
import shutil
import threading
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services import db
from services.generation import GenerationManager
from api import http_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])

# project_id 格式：proj_yyyyMMdd_HHmmss（同秒冲突可追加 _N）
PROJECT_ID_RE = re.compile(r"^proj_\d{8}_\d{6}(_\d+)?$")


class ProjectCreate(BaseModel):
    """创建项目请求体（config 键保持 camelCase，设计 §9）"""
    name: str
    topic: str = ""
    config: dict = {}


# ============================================================
# 分辨率等级 → DB 完整名（V2.4：前端只传等级，方向由画面比例决定）
# 前端值：普清360P / 高清720P / 超清1080P
# DB 值：普清360p 横屏 / 普清360p 竖屏 / ...（与 VideoResolution 枚举一致）
# ============================================================
RESOLUTION_GRADE_MAP = {
    # ratio → 方向后缀
    "16:9": "横屏",
    "1:1": "横屏",  # 1:1 方形默认横屏（与 RESOLUTION_MAP 1:1 key 一致）
    "9:16": "竖屏",
}
_GRADE_BASE_MAP = {
    "普清360P": "普清360p",
    "高清720P": "高清720p",
    "超清1080P": "超清1080p",
}


def _resolve_resolution(grade: str, ratio: str) -> str:
    """前端分辨率等级 + 画面比例 → DB 完整枚举名（带方向）。

    例：("普清360P", "9:16") → "普清360p 竖屏"
    """
    grade_base = _GRADE_BASE_MAP.get(grade)
    suffix = RESOLUTION_GRADE_MAP.get(ratio)
    if grade_base is None or suffix is None:
        raise http_error(400, f"分辨率或画面比例非法: {grade}/{ratio}")
    return f"{grade_base} {suffix}"


# ============================================================
# 创建项目（D2：创建时全量快照）
# ============================================================
@router.post("")
def create_project(body: ProjectCreate):
    """创建项目：读 settings 全量 + 视频配置写入 config_snapshot，status=等待"""
    cfg = body.config or {}
    ratio = str(cfg.get("ratio", "16:9"))
    # V2.4：前端只传等级（普清360P/高清720P/超清1080P），方向由 ratio 决定后落库完整名
    resolution = _resolve_resolution(str(cfg.get("resolution", "普清360P")), ratio)
    fps = int(cfg.get("fps", 16))
    style = str(cfg.get("style", "写实"))
    voice = str(cfg.get("voice", "温柔女声"))
    target_duration = int(cfg.get("targetDuration", cfg.get("target_duration", 30)))
    scene_count = max(3, min(12, target_duration // 5))

    settings = db.load_settings()
    snapshot = {
        "video_config": {
            "ratio": ratio,
            "resolution": resolution,
            "fps": fps,
            "style": style,
            "voice": voice,
            "target_duration": target_duration,
            "scene_count": scene_count,
        },
        "llm": {
            "api_base": settings.get("llm_api_base", ""),
            "api_key": settings.get("llm_api_key", ""),
            "model": settings.get("llm_model", ""),
            "timeout": 300,
        },
        "t2i": {
            "base_url": settings.get("t2i_url", ""),
            "token": settings.get("t2i_token", ""),
            "timeout": int(settings.get("t2i_timeout", "300") or 300),
            "poll_interval": int(settings.get("t2i_poll_interval", "5") or 5),
        },
        "i2v": {
            "base_url": settings.get("i2v_url", ""),
            "token": settings.get("i2v_token", ""),
            "timeout": int(settings.get("i2v_timeout", "300") or 300),
            "poll_interval": int(settings.get("i2v_poll_interval", "10") or 10),
        },
        "tts": {
            "base_url": settings.get("tts_base_url", ""),
            "username": settings.get("tts_username", ""),
            "password": settings.get("tts_password", ""),
        },
    }

    base_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    project_id = base_id
    suffix = 1
    while db.get_project(project_id) is not None:
        project_id = f"{base_id}_{suffix}"
        suffix += 1

    db.insert_project({
        "project_id": project_id,
        "name": body.name.strip(),
        "topic": body.topic.strip(),
        "ratio": ratio,
        "resolution": resolution,
        "fps": fps,
        "style": style,
        "voice": voice,
        "target_duration": target_duration,
        "status": "等待",
        "scene_count": scene_count,
        "config_snapshot": json.dumps(snapshot, ensure_ascii=False),
    })
    logger.info(f"项目创建: {project_id} - {body.name}")
    return {"project_id": project_id, "status": "等待"}


# ============================================================
# 开始生成（单并发锁）
# ============================================================
@router.post("/{project_id}/generate")
def start_generation(project_id: str):
    """单并发锁校验 → 启动后台线程"""
    if not db.get_project(project_id):
        raise http_error(404, "项目不存在")
    if not GenerationManager.try_start(project_id):
        raise http_error(400, "当前已有项目正在创作中")

    thread = threading.Thread(target=GenerationManager.run, args=(project_id,), daemon=True)
    thread.start()
    return {"project_id": project_id, "status": "started"}


@router.post("/{project_id}/stop")
def stop_generation(project_id: str):
    """用户主动停止生成：设 stop flag（后台线程在下一个检查点中断当前 step 并写「失败」状态）。

    阶段路由说明：ComfyUI 阶段（images/videos）会在下一轮询间隔内调 /interrupt 中断 ComfyUI 当前 prompt；
    其他阶段（script/voice/compose）依赖 step 边界或场景循环检测 stop，可能延迟到当前 step 完成后退出。
    """
    if not db.get_project(project_id):
        raise http_error(404, "项目不存在")
    if not GenerationManager.request_stop(project_id):
        raise http_error(400, "该项目未在创作中，无需停止")
    logger.info(f"已请求停止项目 {project_id}")
    return {"project_id": project_id, "status": "stopping"}


# ============================================================
# 状态（DB 为准，step/progress 合并内存）
# ============================================================
@router.get("/{project_id}/status")
def get_status(project_id: str):
    row = db.get_project(project_id)
    if not row:
        raise http_error(404, "项目不存在")

    prog = GenerationManager.get_progress(project_id)
    status = row["status"]
    current_step = ""
    progress = 0
    error_msg = row.get("error_msg") or ""

    # V2.2: status='等待' 但后台生成线程已启动（script 阶段执行中，DB 尚未写「进行中」）
    # 时，返回内存进度，前端 StepFlow 立即显示 script 阶段 running，避免全 pending 空窗。
    if status == "等待" and prog:
        current_step = prog.get("step", "")
        progress = prog.get("progress", 0)

    if status == "进行中":
        current_step = prog.get("step", "")
        progress = prog.get("progress", 0)
    elif status == "完成":
        current_step = "done"
        progress = 100
    elif status == "失败":
        current_step = prog.get("step", "error")
        progress = prog.get("progress", 0)
        error_msg = prog.get("error") or error_msg

    return {
        "project_id": project_id,
        "status": status,
        "current_step": current_step,
        "progress_percent": progress,
        "error_msg": error_msg,
    }


# ============================================================
# 详情（读库 + URL 转换）
# ============================================================
@router.get("/{project_id}")
def get_project_detail(project_id: str):
    row = db.get_project(project_id)
    if not row:
        raise http_error(404, "项目不存在")

    scenes = db.get_scenes(project_id)
    scene_list = []
    for s in scenes:
        scene_list.append({
            "id": s["id"],
            "scene_no": s["scene_no"],
            "duration": s["duration"],
            "description": s["description"],
            "narration": s["narration"],
            "subtitle": s["subtitle"],
            "t2i_prompt": s["t2i_prompt"],
            "i2v_prompt": s["i2v_prompt"],
            "camera": s["camera"],
            "image_url": db.to_file_url(s["image_url"]),
            "video_url": db.to_file_url(s["video_url"]),
            "voice_path": db.to_file_url(s["voice_path"]),
            "voice_duration": s["voice_duration"],
            "status": s["status"],
        })

    cover_rel = db.get_first_scene_image(project_id) or row.get("cover_url", "")

    config = {}
    try:
        snap = json.loads(row.get("config_snapshot") or "{}")
        if isinstance(snap, dict):
            config = snap.get("video_config", {})
    except json.JSONDecodeError:
        config = {}

    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "topic": row["topic"],
        "ratio": row["ratio"],
        "resolution": row["resolution"],
        "fps": row["fps"],
        "style": row["style"],
        "voice": row["voice"],
        "target_duration": row["target_duration"],
        "status": row["status"],
        "error_msg": row["error_msg"],
        "scene_count": row["scene_count"],
        "cover_url": db.to_file_url(cover_rel),
        "final_video_url": db.to_file_url(row.get("final_video_url", "")),
        "download_url": f"/api/projects/{project_id}/download",
        "config": config,
        "scenes": scene_list,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ============================================================
# 列表（分页/筛选/关键词 + cover_url）
# ============================================================
@router.get("")
def list_projects(page: int = 1, page_size: int = 12, status: str = "", keyword: str = ""):
    data = db.list_projects(page=page, page_size=page_size, status=status, keyword=keyword)
    for it in data["items"]:
        it["cover_url"] = db.to_file_url(it.get("cover_path", ""))
        it["final_video_url"] = db.to_file_url(it.get("final_video_url", ""))
        it["download_url"] = f"/api/projects/{it['project_id']}/download"
        it.pop("config_snapshot", None)
        it.pop("cover_path", None)
    return data


# ============================================================
# 删除（级联：行 + scenes + output 目录 + freed_mb）
# ============================================================
@router.delete("/{project_id}")
def delete_project(project_id: str):
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise http_error(400, "非法的项目 ID")
    row = db.get_project(project_id)
    if not row:
        raise http_error(404, "项目不存在")

    proj_dir = db.OUTPUT_DIR / project_id
    freed_bytes = 0
    if proj_dir.exists():
        freed_bytes = sum(f.stat().st_size for f in proj_dir.rglob("*") if f.is_file())
    freed_mb = round(freed_bytes / 1024 / 1024, 1)

    db.delete_scenes(project_id)
    db.delete_project(project_id)
    if proj_dir.exists():
        shutil.rmtree(proj_dir, ignore_errors=True)

    return {"message": "已删除", "freed_mb": freed_mb}


# ============================================================
# 下载成片
# ============================================================
@router.get("/{project_id}/download")
def download_video(project_id: str):
    row = db.get_project(project_id)
    if not row or not row.get("final_video_url"):
        raise http_error(404, "视频未生成")

    rel = row["final_video_url"]
    full = (db.PROJECT_ROOT / rel).resolve()
    if not full.exists() or not full.is_file():
        raise http_error(404, "视频文件不存在")

    return FileResponse(str(full), media_type="video/mp4", filename=f"{row['name']}.mp4")
