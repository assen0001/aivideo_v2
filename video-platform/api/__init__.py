"""API 路由包 — 共享错误响应助手

错误响应统一格式（设计 §9）：{"code": <http_status>, "message": "<中文>", "data": null}
"""

from fastapi import HTTPException


def http_error(status_code: int, message: str) -> HTTPException:
    """构造统一格式的错误响应"""
    return HTTPException(
        status_code=status_code,
        detail={"code": status_code, "message": message, "data": None},
    )
