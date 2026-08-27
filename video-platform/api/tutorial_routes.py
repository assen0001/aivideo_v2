"""教程模块路由（5 接口，P1）

接口：列表 / 详情 / 发布 / 编辑 / 删除
初始内容：启动时 tutorials 空表自动导入 doc/*.md（db.import_docs_if_empty）。
直接发布（is_published=1），无草稿态。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from services import db
from api import http_error
from api.auth_routes import require_auth

router = APIRouter(prefix="/api/tutorials", tags=["tutorials"])


class TutorialBody(BaseModel):
    title: str
    summary: str = ""
    cover: str = ""
    content: str = ""
    tags: str = ""


# ============================================================
# 列表（不含 content）
# ============================================================
@router.get("")
def list_tutorials(tag: str = "", _: dict = Depends(require_auth)):
    items = db.list_tutorials(tag=tag)
    for it in items:
        it.pop("content", None)
    return items


# ============================================================
# 详情（含 Markdown content）
# ============================================================
@router.get("/{tutorial_id}")
def get_tutorial(tutorial_id: int, _: dict = Depends(require_auth)):
    row = db.get_tutorial(tutorial_id)
    if not row:
        raise http_error(404, "教程不存在")
    return row


# ============================================================
# 发布（直接发布）
# ============================================================
@router.post("")
def create_tutorial(body: TutorialBody, _: dict = Depends(require_auth)):
    if not body.title.strip():
        raise http_error(400, "标题不能为空")
    max_order = 0
    existing = db.list_tutorials()
    if existing:
        max_order = max(int(t.get("sort_order", 0) or 0) for t in existing) + 1
    tutorial_id = db.insert_tutorial({
        "title": body.title.strip(),
        "summary": body.summary.strip(),
        "cover": body.cover.strip(),
        "content": body.content,
        "tags": body.tags.strip(),
        "sort_order": max_order,
    })
    return {"message": "发布成功", "id": tutorial_id}


# ============================================================
# 编辑保存（即时生效）
# ============================================================
@router.put("/{tutorial_id}")
def update_tutorial(tutorial_id: int, body: TutorialBody, _: dict = Depends(require_auth)):
    if not db.get_tutorial(tutorial_id):
        raise http_error(404, "教程不存在")
    if not body.title.strip():
        raise http_error(400, "标题不能为空")
    db.update_tutorial(tutorial_id, {
        "title": body.title.strip(),
        "summary": body.summary.strip(),
        "cover": body.cover.strip(),
        "content": body.content,
        "tags": body.tags.strip(),
    })
    return {"message": "已保存"}


# ============================================================
# 删除（无物理文件）
# ============================================================
@router.delete("/{tutorial_id}")
def delete_tutorial(tutorial_id: int, _: dict = Depends(require_auth)):
    if not db.get_tutorial(tutorial_id):
        raise http_error(404, "教程不存在")
    db.delete_tutorial(tutorial_id)
    return {"message": "已删除"}
