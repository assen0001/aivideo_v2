"""认证模块路由（9 接口，P0）

接口：status / setup / captcha / login / logout / reset-password / users me ×2 / 改密
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from services import db
from services import auth_service
from api import http_error

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


# ============================================================
# 鉴权依赖（设计 §2.8：除免鉴权接口外均需 token）
# ============================================================
def require_auth(authorization: Optional[str] = Header(default=None)) -> dict:
    """解析 Authorization: Bearer <token> → verify_token；失败 401"""
    if not authorization or not authorization.startswith("Bearer "):
        raise http_error(401, "未登录或登录已过期")
    token = authorization[len("Bearer "):].strip()
    payload = auth_service.verify_token(token)
    if not payload:
        raise http_error(401, "未登录或登录已过期")
    return payload


# ============================================================
# 请求体模型
# ============================================================
class SetupBody(BaseModel):
    username: str
    password: str
    confirm: str


class LoginBody(BaseModel):
    username: str
    password: str
    captcha_id: str
    code: str


class ResetPasswordBody(BaseModel):
    username: str
    new_password: str
    confirm: str


class UpdateProfileBody(BaseModel):
    nickname: str = ""
    avatar: str = ""
    email: str = ""


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str
    confirm: str


def _public_user(admin: dict) -> dict:
    return {
        "id": admin["id"],
        "username": admin["username"],
        "nickname": admin.get("nickname", ""),
        "avatar": admin.get("avatar", ""),
        "email": admin.get("email", ""),
        "created_at": admin.get("created_at", ""),
    }


# ============================================================
# 接口
# ============================================================
@router.get("/status")
def auth_status():
    """是否已初始化管理员"""
    return {"need_setup": db.get_admin() is None}


@router.post("/setup")
def setup(body: SetupBody):
    """初始化管理员（创建即登录，无验证码）"""
    if db.get_admin() is not None:
        raise http_error(400, "系统已初始化")
    if body.password != body.confirm:
        raise http_error(400, "两次输入的密码不一致")
    if len(body.password) < 6:
        raise http_error(400, "密码长度不能少于 6 位")
    password_hash = auth_service.hash_password(body.password)
    admin_id = db.create_admin(body.username.strip(), password_hash)
    admin = db.get_admin()
    token = auth_service.create_token(admin)
    return {"token": token, "user": _public_user(admin)}


@router.post("/captcha")
def captcha():
    """生成 4 位纯数字 SVG 验证码"""
    captcha_id, svg = auth_service.new_captcha()
    return {"captcha_id": captcha_id, "svg": svg}


@router.post("/login")
def login(body: LoginBody):
    """常规登录：用户名 + 密码 + 验证码"""
    code = auth_service.consume_captcha(body.captcha_id)
    if code is None:
        raise http_error(400, "验证码错误或已过期")
    if code != body.code.strip():
        raise http_error(400, "验证码错误或已过期")

    admin = db.get_admin()
    if not admin or admin["username"] != body.username.strip():
        raise http_error(400, "用户名或密码错误")
    if not auth_service.verify_password(body.password, admin["password_hash"]):
        raise http_error(400, "用户名或密码错误")

    token = auth_service.create_token(admin)
    return {"token": token, "user": _public_user(admin)}


@router.post("/logout")
def logout(_: dict = Depends(require_auth)):
    """登出（token 无状态，前端清 localStorage；幂等）"""
    return {"message": "已退出登录"}


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody):
    """重置密码（成功后 password_version+1 → 旧 token 失效）"""
    admin = db.get_admin()
    if not admin or admin["username"] != body.username.strip():
        raise http_error(400, "用户名不存在")
    if body.new_password != body.confirm:
        raise http_error(400, "两次输入的密码不一致")
    if len(body.new_password) < 6:
        raise http_error(400, "密码长度不能少于 6 位")
    db.update_admin_password(admin["id"], auth_service.hash_password(body.new_password))
    return {"message": "重置成功，请使用新密码登录"}


@users_router.get("/me")
def get_me(payload: dict = Depends(require_auth)):
    """当前用户资料"""
    admin = db.get_admin()
    if not admin:
        raise http_error(401, "未登录或登录已过期")
    return _public_user(admin)


@users_router.put("/me")
def update_me(body: UpdateProfileBody, payload: dict = Depends(require_auth)):
    """修改昵称/头像/邮箱"""
    admin = db.get_admin()
    if not admin:
        raise http_error(401, "未登录或登录已过期")
    db.update_admin_profile(admin["id"], body.nickname.strip(), body.avatar.strip(), body.email.strip())
    updated = db.get_admin()
    return {"message": "已更新", "user": _public_user(updated)}


@users_router.put("/me/password")
def change_password(body: ChangePasswordBody, payload: dict = Depends(require_auth)):
    """修改密码（成功后 password_version+1 + 前端强制重登）"""
    admin = db.get_admin()
    if not admin:
        raise http_error(401, "未登录或登录已过期")
    if not auth_service.verify_password(body.old_password, admin["password_hash"]):
        raise http_error(400, "原密码错误")
    if body.new_password != body.confirm:
        raise http_error(400, "两次输入的密码不一致")
    if len(body.new_password) < 6:
        raise http_error(400, "密码长度不能少于 6 位")
    db.update_admin_password(admin["id"], auth_service.hash_password(body.new_password))
    return {"message": "密码已修改，请重新登录"}
