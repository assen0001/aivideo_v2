"""配置模块路由（5 接口：2 基础 + 3 测试）

接口：GET /api/settings（原始值 + sensitive_keys，前端控制显隐 ④c）
     PUT /api/settings（校验 → 写表 → 刷新缓存立即生效）
     POST /api/settings/test/{vendor}（提交外部 API 连通性测试任务）
     GET  /api/settings/test/{vendor}/{task_id}（轮询测试结果）
     GET  /api/settings/test/preview/{task_id}/{filename}（测试产物预览）
"""

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services import db, testing, auth_service as auth_svc
from api import http_error
from api.auth_routes import require_auth

router = APIRouter(prefix="/api/settings", tags=["settings"])

# 数值型字段：必须为数字且 > 0（R24）
NUMERIC_FIELDS = [
    "t2i_timeout",
    "t2i_poll_interval",
    "i2v_timeout",
    "i2v_poll_interval",
    "upload_doc_img_limit_mb",
    "upload_media_limit_mb",
]


class SettingsBody(BaseModel):
    settings: dict = {}


# ============================================================
# 读取全部配置（原始值 + sensitive_keys）
# ============================================================
@router.get("")
def get_settings(_: dict = Depends(require_auth)):
    data = db.load_settings()
    return {"settings": data, "sensitive_keys": db.SENSITIVE_KEYS}


# ============================================================
# 保存配置（校验 → 写表 → 刷新缓存）
# ============================================================
@router.put("")
def save_settings(body: SettingsBody, _: dict = Depends(require_auth)):
    values = {k: str(v) for k, v in (body.settings or {}).items() if v is not None}

    # 数值校验
    for key in NUMERIC_FIELDS:
        if key in values:
            raw = values[key].strip()
            try:
                num = float(raw)
            except ValueError:
                raise http_error(422, f"字段 {key} 必须为数字")
            if num <= 0:
                raise http_error(422, f"字段 {key} 必须大于 0")

    # 扩展名白名单非空
    if "upload_allow_ext" in values:
        stripped = [e.strip() for e in values["upload_allow_ext"].split(",") if e.strip()]
        if not stripped:
            raise http_error(422, "扩展名白名单不能为空")
        values["upload_allow_ext"] = ",".join(stripped)

    db.save_settings(values)
    return {"message": "保存成功，已生效"}


# ============================================================
# 外部 API 连通性测试（V2.4 新增，结果仅内存，不入库）
# ============================================================
class TestBody(BaseModel):
    settings: dict = {}


@router.post("/test/{vendor}")
def submit_test(vendor: str, body: TestBody, background: BackgroundTasks, _: dict = Depends(require_auth)):
    """提交测试任务，立即返回 task_id；后台异步执行"""
    if vendor not in testing.VENDORS:
        raise http_error(404, f"未知测试类型: {vendor}，可选 {testing.VENDORS}")

    task_id = testing.submit_test(vendor, body.settings or {})
    background.add_task(testing.run_test, vendor, task_id)
    return {"task_id": task_id, "status": "running"}


@router.get("/test/{vendor}/{task_id}")
def poll_test(vendor: str, task_id: str, _: dict = Depends(require_auth)):
    """查询测试任务状态（前端 2s 轮询）"""
    result = testing.get_test_status(task_id)
    if result is None:
        raise http_error(404, "测试任务不存在或已过期")
    return result


@router.get("/test/preview/{task_id}/{filename}")
def test_preview(task_id: str, filename: str, token: str = Query(default="")):
    """返回测试产物文件（仅允许测试临时目录内文件，防穿越）

    鉴权：media 标签无法携带 Authorization header，改用 ?token= 查询参数。
    """
    if not token or not auth_svc.verify_token(token):
        raise http_error(401, "未登录或登录已过期")
    task_dir = Path(testing.TEST_ROOT) / task_id
    root = task_dir.resolve()
    full = (task_dir / filename).resolve()
    if not full.is_relative_to(root) or not full.is_file():
        raise http_error(404, "文件不存在")
    return FileResponse(str(full))
