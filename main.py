"""视频智造平台 V2.0 — FastAPI 后端主入口

启动钩子（lifespan）：
    1. services.db.init_db()                  # 建库建表 + settings 默认值
    2. services.db.import_docs_if_empty(doc/) # 教程初始导入（tutorials 空表时）
    3. services.db.recover_interrupted_projects()  # 进行中 → 失败

路由组织：
    - GET  /api/files/{path}   产物文件访问（output 根，防穿越 403）
    - GET  /upload/{path}      资产文件访问（在 asset_routes 中，防穿越 403）
    - GET  /api/system/status  健康检查（免鉴权）
    - 五组业务路由：auth / projects / assets / tutorials / settings
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 将 video-platform 子目录加入模块搜索路径
sys.path.insert(0, str(Path(__file__).parent / "video-platform"))

from services import db  # noqa: E402
from api import http_error  # noqa: E402
from api.auth_routes import router as auth_router  # noqa: E402
from api.auth_routes import users_router  # noqa: E402
from api.project_routes import router as project_router  # noqa: E402
from api.asset_routes import router as asset_router  # noqa: E402
from api.asset_routes import upload_router  # noqa: E402
from api.tutorial_routes import router as tutorial_router  # noqa: E402
from api.settings_routes import router as settings_router  # noqa: E402

PROJECT_ROOT = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动钩子：建库 → 导入教程 → 恢复中断项目"""
    db.init_db()
    imported = db.import_docs_if_empty(PROJECT_ROOT / "doc")
    if imported:
        print(f"[startup] 已导入 {imported} 篇教程文档")
    recovered = db.recover_interrupted_projects()
    if recovered:
        print(f"[startup] 已恢复 {recovered} 个中断项目 → 失败")
    yield


app = FastAPI(title="视频智造平台 API", version="2.0.0", lifespan=lifespan)

# CORS（允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 统一错误响应（R28）：{"code": <http_status>, "message": "<中文>", "data": null}
# ============================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(detail), "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", []) if x != "body")
        msgs.append(f"{loc}: {e.get('msg', '')}" if loc else e.get("msg", ""))
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数校验失败：" + "；".join(msgs[:3]),
            "data": None,
        },
    )


# ============================================================
# 静态资源（V2.5：音色参考音频 static/speaker/*.mp3 随项目分发）
# ============================================================
app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")


# ============================================================
# 产物文件访问（output 根，防穿越 403）
# ============================================================
@app.get("/api/files/{path:path}")
def serve_file(path: str):
    root = db.OUTPUT_DIR.resolve()
    full = (db.OUTPUT_DIR / path).resolve()
    if not full.is_relative_to(root):
        raise http_error(403, "非法路径")
    if not full.exists() or not full.is_file():
        raise http_error(404, "文件不存在")
    return FileResponse(str(full))


# ============================================================
# 健康检查（免鉴权，工作台"系统状态"小字使用）
# ============================================================
@app.get("/api/system/status")
def system_status():
    from services.comfyui_img import ComfyUIImgClient
    try:
        client = ComfyUIImgClient()
        stats = client.get_system_stats()
        gpu = stats["devices"][0]
        return {
            "status": "ok",
            "gpu": gpu["name"],
            "vram_free_mb": round(gpu["vram_free"] / 1024 / 1024),
            "vram_total_mb": round(gpu["vram_total"] / 1024 / 1024),
            "comfyui_version": stats["system"]["comfyui_version"],
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ============================================================
# 业务路由挂载
# ============================================================
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(project_router)
app.include_router(asset_router)
app.include_router(upload_router)
app.include_router(tutorial_router)
app.include_router(settings_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
