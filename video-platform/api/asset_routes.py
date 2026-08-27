"""资产模块路由（5 接口，P0-P1）

接口：上传 / 列表 / 重命名 / 删除 / /upload 文件访问
限制从 settings 表读取（upload_doc_img_limit_mb / upload_media_limit_mb / upload_allow_ext）。
"""

import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse as FR
from pydantic import BaseModel

from services import db
from api import http_error
from api.auth_routes import require_auth

router = APIRouter(prefix="/api/assets", tags=["assets"])
# /upload 文件访问：独立路由（无 /api/assets 前缀），开发期免鉴权
upload_router = APIRouter(prefix="/upload", tags=["upload"])

# 分类判定（按扩展名，设计 §2.4）
DOC_EXTS = {"pdf", "docx", "xlsx", "pptx", "txt", "md"}
IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
MEDIA_EXTS = {"mp3", "wav", "m4a", "mp4", "webm", "mov"}

# 文件名清理：去路径分隔符 / .. 等危险字符
_SAFE_RE = re.compile(r"[\\/:*?\"<>|\r\n]")


def _sanitize_filename(name: str) -> str:
    name = os.path.basename(name.replace("\\", "/"))
    name = _SAFE_RE.sub("_", name).strip()
    return name or "file"


def _dedupe_name(target_dir: Path, file_name: str) -> str:
    """目标已存在则追加 (1)、(2)"""
    stem, ext = os.path.splitext(file_name)
    candidate = file_name
    idx = 1
    while (target_dir / candidate).exists():
        candidate = f"{stem}({idx}){ext}"
        idx += 1
    return candidate


class RenameBody(BaseModel):
    file_name: str


# ============================================================
# 上传（multipart，python-multipart）
# ============================================================
@router.post("/upload")
async def upload_assets(files: List[UploadFile] = File(...), _: dict = Depends(require_auth)):
    settings = db.load_settings()
    allow_ext = [e.strip().lower() for e in settings.get("upload_allow_ext", "").split(",") if e.strip()]
    doc_img_limit = int(float(settings.get("upload_doc_img_limit_mb", "10") or 10) * 1024 * 1024)
    media_limit = int(float(settings.get("upload_media_limit_mb", "30") or 30) * 1024 * 1024)

    items = []
    failures = []

    for f in files:
        original = f.filename or "file"
        safe_name = _sanitize_filename(original)
        ext = os.path.splitext(safe_name)[1].lstrip(".").lower()

        if not ext or ext not in allow_ext:
            failures.append({"file_name": original, "reason": f"扩展名 .{ext} 不在白名单内"})
            continue

        if ext in DOC_EXTS:
            subdir, ftype, limit = "docs", "文档", doc_img_limit
        elif ext in IMAGE_EXTS:
            subdir, ftype, limit = "images", "图片", doc_img_limit
        elif ext in MEDIA_EXTS:
            subdir, ftype, limit = "media", "音视频", media_limit
        else:
            subdir, ftype, limit = "docs", "其他", doc_img_limit

        content = await f.read()
        size = len(content)
        if size > limit:
            failures.append({
                "file_name": original,
                "reason": f"超过大小限制 {limit // 1024 // 1024}MB",
            })
            continue

        target_dir = db.UPLOAD_DIR / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        final_name = _dedupe_name(target_dir, safe_name)
        (target_dir / final_name).write_bytes(content)

        rel = f"upload/{subdir}/{final_name}"
        asset_id = db.insert_asset({
            "file_name": safe_name,
            "file_type": ftype,
            "ext": ext,
            "file_size": size,
            "file_path": rel,
        })
        items.append({
            "id": asset_id,
            "file_name": safe_name,
            "file_type": ftype,
            "ext": ext,
            "file_size": size,
            "file_path": rel,
            "url": db.to_upload_url(rel),
            "created_at": "",
        })

    if failures and not items:
        detail = "；".join(f"{x['file_name']}: {x['reason']}" for x in failures[:5])
        raise http_error(400, f"上传失败：{detail}")

    return {"items": items, "failures": failures}


# ============================================================
# 列表（类型筛选 + 关键词 + 分页）
# ============================================================
@router.get("")
def list_assets(type: str = "全部", keyword: str = "", page: int = 1, page_size: int = 20,
                _: dict = Depends(require_auth)):
    data = db.list_assets(file_type=type, keyword=keyword, page=page, page_size=page_size)
    for it in data["items"]:
        it["url"] = db.to_upload_url(it["file_path"])
    return data


# ============================================================
# 重命名（仅重命名，保留原扩展名）
# ============================================================
@router.put("/{asset_id}")
def rename_asset(asset_id: int, body: RenameBody, _: dict = Depends(require_auth)):
    asset = db.get_asset(asset_id)
    if not asset:
        raise http_error(404, "资产不存在")

    new_name = _sanitize_filename(body.file_name)
    if not new_name:
        raise http_error(400, "文件名不能为空")

    old_ext = asset.get("ext", "").lower()
    new_ext = os.path.splitext(new_name)[1].lstrip(".").lower()
    if new_ext and old_ext and new_ext != old_ext:
        raise http_error(400, "不能修改扩展名")
    if not new_ext and old_ext:
        new_name = f"{new_name}.{old_ext}"

    # 物理文件同步重命名（file_path 相对项目根 upload/docs/xx → upload 根路径）
    rel = asset["file_path"]
    old_path = db.upload_abs_path(rel)
    # 新相对路径：同子目录 + 新文件名（P1 修复：os.rename 成功后 DB file_path 必须同步）
    new_rel = str(Path(rel).parent / new_name).replace("\\", "/")
    if old_path.exists():
        new_path = db.upload_abs_path(new_rel)
        if new_path != old_path:
            if new_path.exists():
                raise http_error(400, "同名文件已存在")
            os.rename(old_path, new_path)
        db.rename_asset(asset_id, new_name, new_rel)
        return {"message": "已重命名", "file_name": new_name, "file_path": new_rel}

    # 物理文件缺失（历史脏数据）：仅同步 DB，保持 file_name/file_path 一致
    db.rename_asset(asset_id, new_name, new_rel)
    return {"message": "已重命名", "file_name": new_name, "file_path": new_rel}


# ============================================================
# 删除（级联物理文件）
# ============================================================
@router.delete("/{asset_id}")
def delete_asset(asset_id: int, _: dict = Depends(require_auth)):
    asset = db.get_asset(asset_id)
    if not asset:
        raise http_error(404, "资产不存在")

    freed_bytes = int(asset.get("file_size", 0) or 0)
    freed_mb = round(freed_bytes / 1024 / 1024, 1)
    warn = ""

    rel = asset["file_path"]
    full = db.upload_abs_path(rel).resolve()
    try:
        if full.is_file() and full.is_relative_to(db.UPLOAD_DIR.resolve()):
            os.remove(full)
    except OSError:
        # 物理删除失败不阻塞记录删除，但显式提示（P2：避免静默吞掉）
        warn = "；物理文件删除失败，请手动清理"

    db.delete_asset(asset_id)
    return {"message": "已删除" + warn, "freed_mb": freed_mb, "warn": warn}


# ============================================================
# /upload 文件访问（打开/下载，防路径穿越 403；开发期免鉴权）
# ============================================================
@upload_router.get("/{path:path}")
def serve_upload(path: str):
    root = db.UPLOAD_DIR.resolve()
    full = (db.UPLOAD_DIR / path).resolve()
    if not full.is_relative_to(root):
        raise http_error(403, "非法路径")
    if not full.exists() or not full.is_file():
        raise http_error(404, "文件不存在")
    return FR(str(full))
