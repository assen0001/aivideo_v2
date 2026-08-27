"""认证服务 — 密码 / token / SVG 验证码（V2.0，零新增依赖）

- 密码：PBKDF2-SHA256，盐 16B 随机，迭代 200_000
- token：HMAC-SHA256 自实现签名（payload 含 uid/username/pwd_ver/exp），7 天有效期
- 验证码：6 位纯数字，纯 SVG 生成，120s 一次性（内存 dict）
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Optional, Tuple

from services import db

# token 有效期（秒）：7 天
TOKEN_TTL = 7 * 24 * 3600
# 验证码有效期（秒）：120
CAPTCHA_TTL = 120
# 签名密钥：启动时随机生成（内存，不落盘）
_SECRET = secrets.token_hex(32)

# 验证码缓存：captcha_id -> {"code": ..., "exp": ...}
_captchas: Dict[str, Dict[str, object]] = {}


# ============================================================
# 密码（PBKDF2-SHA256）
# ============================================================
def hash_password(password: str) -> str:
    """生成 PBKDF2 密文：pbkdf2_sha256$iter$salt$hash"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000)
    return f"pbkdf2_sha256${200_000}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码（恒定时间比较）"""
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


# ============================================================
# token（HMAC-SHA256 自实现）
# ============================================================
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_token(admin: dict) -> str:
    """签发 token：body.sig（body 为 base64url(JSON payload)）"""
    payload = {
        "uid": admin["id"],
        "username": admin["username"],
        "pwd_ver": int(admin.get("password_version", 0)),
        "exp": int(time.time()) + TOKEN_TTL,
    }
    body = _b64url_encode(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sig = _b64url_encode(hmac.new(_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_token(token: str) -> Optional[dict]:
    """校验 token：签名 → 有效期 → DB admin.password_version 比对 pwd_ver；任一失败返回 None"""
    try:
        body, sig = token.split(".")
        expected = hmac.new(_SECRET.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(sig)
        if not hmac.compare_digest(actual, expected):
            return None

        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None

        admin = db.get_admin()
        if not admin:
            return None
        if int(admin["id"]) != int(payload.get("uid", -1)):
            return None
        if int(admin.get("password_version", 0)) != int(payload.get("pwd_ver", -1)):
            return None
        return payload
    except Exception:
        return None


# ============================================================
# 验证码（4 位纯数字，纯 SVG）
# ============================================================
def new_captcha() -> Tuple[str, str]:
    """生成验证码，返回 (captcha_id, svg_string)"""
    code = "".join(str(secrets.randbelow(10)) for _ in range(4))
    captcha_id = secrets.token_hex(16)
    _captchas[captcha_id] = {"code": code, "exp": time.time() + CAPTCHA_TTL}
    return captcha_id, render_svg(code)


def consume_captcha(captcha_id: str) -> Optional[str]:
    """取用即删（一次性）；过期返回 None"""
    item = _captchas.pop(captcha_id, None)
    if not item:
        return None
    if time.time() > float(item["exp"]):
        return None
    return str(item["code"])


def render_svg(code: str) -> str:
    """纯字符串拼 SVG：米白背景 + 噪点线 + 4 数字随机位置/旋转/颜色，零依赖"""
    import random
    random.seed(code)
    width, height = 140, 48
    colors = ["#C08552", "#E08A3C", "#6F9A5E", "#C25E4C", "#5B7FA6", "#8A6BB8"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" rx="8" fill="#FBF4E9"/>',
    ]
    # 噪点线（3 条）
    for _ in range(3):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{random.choice(colors)}" '
            f'stroke-width="1" opacity="0.35"/>'
        )
    # 4 位数字（随机位置/旋转/颜色）
    step = width / (len(code) + 1)
    for i, ch in enumerate(code):
        cx = step * (i + 1)
        cy = 30 + random.randint(-4, 4)
        rot = random.randint(-18, 18)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" transform="rotate({rot} {cx:.1f} {cy:.1f})" '
            f'font-family="monospace" font-size="26" font-weight="bold" '
            f'fill="{random.choice(colors)}" text-anchor="middle">{ch}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
