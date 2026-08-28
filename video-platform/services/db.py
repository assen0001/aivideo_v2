"""SQLite 数据访问层（DAO）— V2.0 唯一数据源

职责：
- 连接管理：WAL + busy_timeout(5000)，短事务（每 DAO 方法一次提交）
- 六表 CRUD：admin / projects / scenes / assets / tutorials / settings
- settings 配置缓存 + 刷新（PUT /api/settings 后立即生效）
- 教程 doc/*.md 初始导入（tutorials 空表时）
- 启动恢复钩子：把「进行中」项目置为「失败」

约定（设计 §9）：
- 数据库/后端字段一律 snake_case
- DB 存相对项目根路径（output/...、upload/...）；访问 URL 由 to_file_url / to_upload_url 转换
- 写操作一律短事务，禁止跨步骤持有连接
"""

import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================
# 路径常量（相对项目根）
# ============================================================
# db.py 位于 D:\aivideo_v2\video-platform\services\db.py
PROJECT_ROOT = Path(__file__).parent.parent.parent          # D:\aivideo_v2
DB_PATH = PROJECT_ROOT / "sqlite" / "aivideo.db"
OUTPUT_DIR = PROJECT_ROOT / "output"
UPLOAD_DIR = PROJECT_ROOT / "upload"

# ============================================================
# settings 默认值（需求 §4.3，领导提供）
# ============================================================
DEFAULT_SETTINGS: Dict[str, str] = {
    "llm_api_base": "http://127.0.0.1:1234/v1",
    "llm_api_key": "api-key",
    "llm_model": "qwen3.8-27b",
    "t2i_url": "http://127.0.0.1:8080",
    "t2i_token": "api-key",
    "t2i_timeout": "300",
    "t2i_poll_interval": "5",
    "i2v_url": "http://127.0.0.1:8080",
    "i2v_token": "api-key",
    "i2v_timeout": "300",
    "i2v_poll_interval": "10",
    "tts_base_url": "http://127.0.0.1:7860",
    "tts_username": "user",
    "tts_password": "password",
    "upload_doc_img_limit_mb": "10",
    "upload_media_limit_mb": "30",
    "upload_allow_ext": "pdf,docx,xlsx,pptx,txt,md,png,jpg,jpeg,webp,gif,mp3,wav,m4a,mp4,webm,mov",
}

# settings 敏感字段（前端掩码显隐，§9 约定）
SENSITIVE_KEYS = ["llm_api_key", "t2i_token", "i2v_token", "tts_password"]

# ============================================================
# 连接管理
# ============================================================
_lock = threading.Lock()
_settings_cache: Dict[str, str] = {}
_settings_loaded = False


def get_connection() -> sqlite3.Connection:
    """创建数据库连接：WAL + busy_timeout(5000)，row_factory=Row"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _now() -> str:
    return "datetime('now','localtime')"


# ============================================================
# 建库建表（幂等）
# ============================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS admin (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  nickname      TEXT DEFAULT '',
  avatar        TEXT DEFAULT '',
  email         TEXT DEFAULT '',
  password_version INTEGER DEFAULT 0,
  created_at    TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS projects (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id      TEXT UNIQUE NOT NULL,
  name            TEXT NOT NULL,
  topic           TEXT DEFAULT '',
  ratio           TEXT DEFAULT '16:9',
  resolution      TEXT DEFAULT '普清360p 横屏',
  fps             INTEGER DEFAULT 16,
  style           TEXT DEFAULT '写实',
  voice           TEXT DEFAULT '温柔女声',
  target_duration INTEGER DEFAULT 30,
  status          TEXT DEFAULT '等待',
  error_msg       TEXT DEFAULT '',
  scene_count     INTEGER DEFAULT 0,
  cover_url       TEXT DEFAULT '',
  final_video_url TEXT DEFAULT '',
  config_snapshot TEXT DEFAULT '',
  created_at      TEXT DEFAULT (datetime('now','localtime')),
  updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS scenes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id    TEXT NOT NULL REFERENCES projects(project_id),
  scene_no      INTEGER NOT NULL,
  duration      REAL DEFAULT 5,
  description   TEXT DEFAULT '',
  narration     TEXT DEFAULT '',
  subtitle      TEXT DEFAULT '',
  t2i_prompt    TEXT DEFAULT '',
  i2v_prompt    TEXT DEFAULT '',
  camera        TEXT DEFAULT '',
  image_url     TEXT DEFAULT '',
  video_url     TEXT DEFAULT '',
  voice_path    TEXT DEFAULT '',
  voice_duration REAL DEFAULT 0,
  status        TEXT DEFAULT '待生成',
  UNIQUE(project_id, scene_no)
);

CREATE TABLE IF NOT EXISTS assets (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  file_name  TEXT NOT NULL,
  file_type  TEXT NOT NULL,
  ext        TEXT DEFAULT '',
  file_size  INTEGER NOT NULL,
  file_path  TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS tutorials (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT NOT NULL,
  summary     TEXT DEFAULT '',
  cover       TEXT DEFAULT '',
  content     TEXT DEFAULT '',
  tags        TEXT DEFAULT '',
  is_published INTEGER DEFAULT 1,
  sort_order  INTEGER DEFAULT 0,
  created_at  TEXT DEFAULT (datetime('now','localtime')),
  updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS settings (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  key        TEXT UNIQUE NOT NULL,
  value      TEXT DEFAULT '',
  updated_at TEXT DEFAULT (datetime('now','localtime'))
);
"""


def init_db() -> None:
    """建库建表（幂等）+ settings 为空则插入默认值"""
    with closing(get_connection()) as conn:
        with conn:
            conn.executescript(_SCHEMA)
        row = conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()
        if row["c"] == 0:
            with conn:
                for key, value in DEFAULT_SETTINGS.items():
                    conn.execute(
                        "INSERT INTO settings(key, value) VALUES(?, ?)",
                        (key, value),
                    )
    refresh_settings_cache()


# ============================================================
# settings 缓存
# ============================================================
def load_settings() -> Dict[str, str]:
    """读取全部 settings（首次查库并缓存）"""
    global _settings_loaded
    with _lock:
        if _settings_loaded and _settings_cache:
            return dict(_settings_cache)
        data: Dict[str, str] = {}
        with closing(get_connection()) as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        for r in rows:
            data[r["key"]] = r["value"]
        _settings_cache.clear()
        _settings_cache.update(data)
        _settings_loaded = True
        return dict(data)


def refresh_settings_cache() -> Dict[str, str]:
    """重新查库并刷新缓存（PUT /api/settings 后调用，立即生效）"""
    global _settings_loaded
    with _lock:
        _settings_loaded = False
    return load_settings()


def get_setting(key: str, default: str = "") -> str:
    """读取单个配置项；缓存未就绪时先加载"""
    try:
        data = load_settings()
    except Exception:
        return DEFAULT_SETTINGS.get(key, default)
    return data.get(key, default if default != "" else DEFAULT_SETTINGS.get(key, ""))


def save_settings(values: Dict[str, str]) -> None:
    """批量保存配置（UPSERT）并刷新缓存"""
    with closing(get_connection()) as conn:
        with conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, datetime('now','localtime')) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now','localtime')",
                    (key, str(value)),
                )
    refresh_settings_cache()


# ============================================================
# URL 构造（D5：DB 存相对路径，URL 由后端统一转换）
# ============================================================
def to_file_url(rel_path: str) -> str:
    """output 产物相对路径 -> /api/files/{path}（去掉 output/ 前缀，避免双 output/ 路径）

    DB 存的是项目根相对路径（output/proj_xxx/...）；后端 /api/files 的根是 OUTPUT_DIR (= output/),
    故 URL 必须去掉 output/，否则会拼成 output/output/... 找不到文件。
    """
    if not rel_path:
        return ""
    p = str(rel_path).replace("\\", "/")
    if p.startswith("output/"):
        p = p[len("output/"):]
    return "/api/files/" + p


def to_upload_url(rel_path: str) -> str:
    """资产相对项目根路径 -> /upload/{path}（path 相对 upload 根，去掉 upload/ 前缀）"""
    if not rel_path:
        return ""
    p = str(rel_path).replace("\\", "/")
    if p.startswith("upload/"):
        p = p[len("upload/"):]
    return "/upload/" + p


def upload_abs_path(rel_path: str):
    """资产相对项目根路径（upload/docs/xx）-> upload 根下的绝对路径"""
    p = str(rel_path).replace("\\", "/")
    if p.startswith("upload/"):
        p = p[len("upload/"):]
    return UPLOAD_DIR / p


def relpath_of(path: Optional[str]) -> str:
    """绝对路径 -> 相对项目根（正斜杠）；None/空 -> ''"""
    if not path:
        return ""
    p = os.path.abspath(str(path))
    try:
        rel = os.path.relpath(p, str(PROJECT_ROOT))
    except ValueError:
        return ""
    return rel.replace("\\", "/")


# ============================================================
# admin（单用户）
# ============================================================
def get_admin() -> Optional[Dict[str, Any]]:
    """返回唯一管理员（无则 None）"""
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM admin ORDER BY id LIMIT 1").fetchone()
    return dict(row) if row else None


def create_admin(username: str, password_hash: str,
                 nickname: str = "", avatar: str = "", email: str = "") -> int:
    """创建管理员，返回 id"""
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO admin(username, password_hash, nickname, avatar, email) VALUES(?, ?, ?, ?, ?)",
                (username, password_hash, nickname, avatar, email),
            )
            return int(cur.lastrowid)


def update_admin_profile(admin_id: int, nickname: str, avatar: str, email: str) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE admin SET nickname=?, avatar=?, email=? WHERE id=?",
                (nickname, avatar, email, admin_id),
            )


def update_admin_password(admin_id: int, password_hash: str) -> None:
    """改密/重置：password_version + 1（旧 token 失效 → 强制重登）"""
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE admin SET password_hash=?, password_version=password_version+1 WHERE id=?",
                (password_hash, admin_id),
            )


# ============================================================
# projects
# ============================================================
def insert_project(row: Dict[str, Any]) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO projects(project_id, name, topic, ratio, resolution, fps, style, voice, "
                "target_duration, status, error_msg, scene_count, cover_url, final_video_url, config_snapshot, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
                (
                    row["project_id"], row["name"], row.get("topic", ""),
                    row.get("ratio", "16:9"), row.get("resolution", "普清360p 横屏"),
                    int(row.get("fps", 16)), row.get("style", "写实"), row.get("voice", "温柔女声"),
                    int(row.get("target_duration", 30)), row.get("status", "等待"),
                    row.get("error_msg", ""), int(row.get("scene_count", 0)),
                    row.get("cover_url", ""), row.get("final_video_url", ""),
                    row.get("config_snapshot", ""),
                ),
            )


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
    return dict(row) if row else None


def list_projects(page: int = 1, page_size: int = 12,
                  status: str = "", keyword: str = "") -> Dict[str, Any]:
    """项目分页列表；items 带 cover_path（第 1 分镜 image_url，IN 子查询一次取回）"""
    page = max(1, int(page))
    page_size = max(1, int(page_size))
    where, params = [], []
    if status and status != "全部":
        where.append("status = ?")
        params.append(status)
    if keyword:
        where.append("(name LIKE ? OR topic LIKE ?)")
        kw = f"%{keyword}%"
        params.extend([kw, kw])
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with closing(get_connection()) as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM projects {where_sql}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM projects {where_sql} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        items = [dict(r) for r in rows]

    # 封面：IN 子查询一次取回所有项目的第 1 分镜 image_url
    ids = [it["project_id"] for it in items]
    cover_map: Dict[str, str] = {}
    if ids:
        marks = ",".join("?" for _ in ids)
        with closing(get_connection()) as conn:
            cover_rows = conn.execute(
                f"SELECT s.project_id, s.image_url FROM scenes s "
                f"JOIN (SELECT project_id, MIN(scene_no) AS min_no FROM scenes "
                f"WHERE project_id IN ({marks}) GROUP BY project_id) t "
                f"ON s.project_id = t.project_id AND s.scene_no = t.min_no",
                ids,
            ).fetchall()
        for cr in cover_rows:
            cover_map[cr["project_id"]] = cr["image_url"] or ""

    for it in items:
        it["cover_path"] = cover_map.get(it["project_id"], "") or it.get("cover_url", "")

    has_more = page * page_size < total
    return {"items": items, "total": total, "page": page, "page_size": page_size, "has_more": has_more}


def update_project_status(project_id: str, status: str, error_msg: str = "") -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE projects SET status=?, error_msg=?, updated_at=datetime('now','localtime') WHERE project_id=?",
                (status, error_msg, project_id),
            )


def update_project_scene_count(project_id: str, n: int) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE projects SET scene_count=?, updated_at=datetime('now','localtime') WHERE project_id=?",
                (int(n), project_id),
            )


def update_project_final(project_id: str, final_video_url: str) -> None:
    """compose 完成：status=完成 + final_video_url（相对路径）+ updated_at"""
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE projects SET status='完成', final_video_url=?, error_msg='', "
                "updated_at=datetime('now','localtime') WHERE project_id=?",
                (final_video_url, project_id),
            )


def delete_project(project_id: str) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("DELETE FROM projects WHERE project_id=?", (project_id,))


# ============================================================
# scenes
# ============================================================
def upsert_scenes(project_id: str, scenes: List[Dict[str, Any]]) -> None:
    """全量替换：DELETE + INSERT 一个事务（短事务）"""
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("DELETE FROM scenes WHERE project_id=?", (project_id,))
            conn.executemany(
                "INSERT INTO scenes(project_id, scene_no, duration, description, narration, subtitle, "
                "t2i_prompt, i2v_prompt, camera, image_url, video_url, voice_path, voice_duration, status) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        project_id,
                        int(s["scene_no"]), float(s.get("duration", 5)),
                        s.get("description", ""), s.get("narration", ""), s.get("subtitle", ""),
                        s.get("t2i_prompt", ""), s.get("i2v_prompt", ""), s.get("camera", ""),
                        s.get("image_url", ""), s.get("video_url", ""), s.get("voice_path", ""),
                        float(s.get("voice_duration", 0) or 0), s.get("status", "待生成"),
                    )
                    for s in scenes
                ],
            )


def upsert_scene(project_id: str, scene: Dict[str, Any]) -> None:
    """单条 upsert（project_id + scene_no 冲突时更新产物字段），短事务。

    分镜级实时写库使用：每生成一个分镜产物（图片/视频/语音）立即写库，
    前端 3s 轮询详情即可看到该分镜，无需等整个阶段跑完。
    依赖 scenes 表 UNIQUE(project_id, scene_no) 约束（SQLite ON CONFLICT DO UPDATE，需 3.24+）。
    """
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO scenes(project_id, scene_no, duration, description, narration, subtitle, "
                "t2i_prompt, i2v_prompt, camera, image_url, video_url, voice_path, voice_duration, status) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(project_id, scene_no) DO UPDATE SET "
                "duration=excluded.duration, description=excluded.description, narration=excluded.narration, "
                "subtitle=excluded.subtitle, t2i_prompt=excluded.t2i_prompt, i2v_prompt=excluded.i2v_prompt, "
                "camera=excluded.camera, image_url=excluded.image_url, video_url=excluded.video_url, "
                "voice_path=excluded.voice_path, voice_duration=excluded.voice_duration, status=excluded.status",
                (
                    project_id,
                    int(scene["scene_no"]), float(scene.get("duration", 5)),
                    scene.get("description", ""), scene.get("narration", ""), scene.get("subtitle", ""),
                    scene.get("t2i_prompt", ""), scene.get("i2v_prompt", ""), scene.get("camera", ""),
                    scene.get("image_url", ""), scene.get("video_url", ""), scene.get("voice_path", ""),
                    float(scene.get("voice_duration", 0) or 0), scene.get("status", "待生成"),
                ),
            )


def get_scenes(project_id: str) -> List[Dict[str, Any]]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT * FROM scenes WHERE project_id=? ORDER BY scene_no ASC",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_first_scene_image(project_id: str) -> str:
    with closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT image_url FROM scenes WHERE project_id=? AND image_url != '' "
            "ORDER BY scene_no ASC LIMIT 1",
            (project_id,),
        ).fetchone()
    return row["image_url"] if row else ""


def delete_scenes(project_id: str) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("DELETE FROM scenes WHERE project_id=?", (project_id,))


# ============================================================
# assets
# ============================================================
def insert_asset(row: Dict[str, Any]) -> int:
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO assets(file_name, file_type, ext, file_size, file_path) VALUES(?, ?, ?, ?, ?)",
                (row["file_name"], row["file_type"], row.get("ext", ""),
                 int(row["file_size"]), row["file_path"]),
            )
            return int(cur.lastrowid)


def list_assets(file_type: str = "", keyword: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    page = max(1, int(page))
    page_size = max(1, int(page_size))
    where, params = [], []
    if file_type and file_type != "全部":
        where.append("file_type = ?")
        params.append(file_type)
    if keyword:
        where.append("file_name LIKE ?")
        params.append(f"%{keyword}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with closing(get_connection()) as conn:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM assets {where_sql}", params).fetchone()["c"]
        rows = conn.execute(
            f"SELECT * FROM assets {where_sql} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [page_size, (page - 1) * page_size],
        ).fetchall()
        items = [dict(r) for r in rows]

    has_more = page * page_size < total
    return {"items": items, "total": total, "page": page, "page_size": page_size, "has_more": has_more}


def get_asset(asset_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM assets WHERE id=?", (int(asset_id),)).fetchone()
    return dict(row) if row else None


def rename_asset(asset_id: int, file_name: str, file_path: Optional[str] = None) -> None:
    """资产重命名：更新 file_name；传入 file_path 时同步更新（修复重命名后路径不同步 P1）"""
    with closing(get_connection()) as conn:
        with conn:
            if file_path is not None:
                conn.execute(
                    "UPDATE assets SET file_name=?, file_path=? WHERE id=?",
                    (file_name, file_path, int(asset_id)),
                )
            else:
                conn.execute(
                    "UPDATE assets SET file_name=? WHERE id=?",
                    (file_name, int(asset_id)),
                )


def delete_asset(asset_id: int) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("DELETE FROM assets WHERE id=?", (int(asset_id),))


# ============================================================
# tutorials
# ============================================================
def count_tutorials() -> int:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM tutorials").fetchone()
    return int(row["c"])


def list_tutorials(tag: str = "") -> List[Dict[str, Any]]:
    """列表不含 content；排序 sort_order ASC, id DESC"""
    sql = "SELECT id, title, summary, cover, tags, is_published, sort_order, created_at, updated_at FROM tutorials"
    params: List[Any] = []
    if tag:
        sql += " WHERE tags LIKE ?"
        params.append(f"%{tag}%")
    sql += " ORDER BY sort_order ASC, id DESC"
    with closing(get_connection()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_tutorial(tutorial_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_connection()) as conn:
        row = conn.execute("SELECT * FROM tutorials WHERE id=?", (int(tutorial_id),)).fetchone()
    return dict(row) if row else None


def _sanitize_text(val: Any) -> Any:
    """剔除代理对（lone surrogates，如 \\udcb6）。

    SQLite 的 Python 驱动会用 UTF-8 编码参数，代理对字符无法编码，
    会抛出 UnicodeEncodeError；且该字符一旦进入异常信息，连 print/logging 都会二次崩溃。
    """
    if not isinstance(val, str):
        return val
    return "".join(ch for ch in val if not (0xD800 <= ord(ch) <= 0xDFFF))


def insert_tutorial(row: Dict[str, Any]) -> int:
    # 对所有文本字段兜底清洗，杜绝任何来源的代理对字符写入 SQLite
    title = _sanitize_text(str(row.get("title", "")))
    summary = _sanitize_text(str(row.get("summary", "")))
    cover = _sanitize_text(str(row.get("cover", "")))
    content = _sanitize_text(str(row.get("content", "")))
    tags = _sanitize_text(str(row.get("tags", "")))
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO tutorials(title, summary, cover, content, tags, is_published, sort_order, updated_at) "
                "VALUES(?, ?, ?, ?, ?, 1, ?, datetime('now','localtime'))",
                (title, summary, cover, content, tags, int(row.get("sort_order", 0))),
            )
            return int(cur.lastrowid)


def update_tutorial(tutorial_id: int, row: Dict[str, Any]) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                "UPDATE tutorials SET title=?, summary=?, cover=?, content=?, tags=?, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (row["title"], row.get("summary", ""), row.get("cover", ""),
                 row.get("content", ""), row.get("tags", ""), int(tutorial_id)),
            )


def delete_tutorial(tutorial_id: int) -> None:
    with closing(get_connection()) as conn:
        with conn:
            conn.execute("DELETE FROM tutorials WHERE id=?", (int(tutorial_id),))


# ============================================================
# 启动钩子
# ============================================================
def import_docs_if_empty(doc_dir: Path) -> int:
    """tutorials 空表时导入 doc/*.md 全部文档（容错：单文件/单字符异常均不影响启动）"""
    try:
        if count_tutorials() > 0:
            return 0
        doc_path = Path(doc_dir)
        if not doc_path.exists():
            return 0
        md_files = sorted(doc_path.glob("*.md"))
        imported = 0
        for idx, f in enumerate(md_files):
            try:
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    # 读取都失败则跳过该文件，不阻塞整体启动
                    _safe_log(f"[startup] 读取教程失败（跳过）: {f.name}")
                    continue
                # 去除代理对/非法字符（双重保险，insert_tutorial 内也会清洗）
                content = _sanitize_text(content)
                summary = _sanitize_text(content[:100].replace("\n", " ").strip())
                insert_tutorial({
                    "title": f.stem,
                    "summary": summary,
                    "cover": "",
                    "content": content,
                    "tags": "项目文档",
                    "sort_order": idx,
                })
                imported += 1
            except Exception as e:
                # 单篇导入失败只跳过，且日志打印本身也要防代理对二次崩溃
                _safe_log(f"[startup] 导入教程失败（已跳过）: {f.name} -> {_sanitize_text(str(e))}")
        return imported
    except Exception as e:
        _safe_log(f"[startup] import_docs_if_empty 异常（已忽略，不影响启动）: {_sanitize_text(str(e))}")
        return 0


def _safe_log(msg: str) -> None:
    """日志打印，msg 中的代理对字符先清洗，避免 print 二次抛 UnicodeEncodeError。"""
    try:
        print(_sanitize_text(str(msg)), flush=True)
    except Exception:
        pass


def recover_interrupted_projects() -> int:
    """启动时：进行中 → 失败（线程任务无法续跑，② 决策）"""
    with closing(get_connection()) as conn:
        with conn:
            cur = conn.execute(
                "UPDATE projects SET status='失败', error_msg='服务重启，生成中断，请重新生成', "
                "updated_at=datetime('now','localtime') WHERE status='进行中'"
            )
            return int(cur.rowcount)
