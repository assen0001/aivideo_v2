# 视频智造平台 — API 对接说明

> **项目名称：** 本地视频智造平台（英文简称 aivideo）
> **文档版本：** v2.0（合并稿）
> **基础 URL：** `http://localhost:8000`
> **Swagger 文档：** `http://localhost:8000/docs`（ReDoc: `/redoc`）
> **格式：** JSON
> **编制日期：** 2026-08-25

---

## 目录

1. [接口总览](#1-接口总览)
2. [通用约定](#2-通用约定)
3. [认证接口](#3-认证接口)
4. [用户接口](#4-用户接口)
5. [项目管理接口](#5-项目管理接口)
6. [资产接口](#6-资产接口)
7. [教程接口](#7-教程接口)
8. [配置接口](#8-配置接口)
9. [系统状态与文件服务](#9-系统状态与文件服务)
10. [前端调用示例](#10-前端调用示例)
11. [接口变更记录](#11-接口变更记录)

---

## 1. 接口总览

### 1.1 认证（9 + 3）

| # | 方法 | 路径 | 说明 |
|:--:|:----:|:-----|:-----|
| 1 | GET | `/api/auth/status` | 查询初始化状态（need_setup） |
| 2 | POST | `/api/auth/setup` | 初始化管理员（创建即登录） |
| 3 | POST | `/api/auth/captcha` | 获取登录验证码（SVG） |
| 4 | POST | `/api/auth/login` | 登录 |
| 5 | POST | `/api/auth/logout` | 登出 |
| 6 | POST | `/api/auth/reset-password` | 重置密码 |
| 7 | GET | `/api/users/me` | 获取当前用户资料 |
| 8 | PUT | `/api/users/me` | 修改用户资料 |
| 9 | PUT | `/api/users/me/password` | 修改密码 |

### 1.2 项目（7）

| # | 方法 | 路径 | 说明 |
|:--:|:----:|:-----|:-----|
| 10 | POST | `/api/projects` | 创建视频项目 |
| 11 | POST | `/api/projects/{project_id}/generate` | 开始生成视频（异步，单并发） |
| 12 | GET | `/api/projects/{project_id}/status` | 查询生成状态 |
| 13 | GET | `/api/projects/{project_id}` | 获取项目详情 |
| 14 | GET | `/api/projects` | 项目列表（分页/筛选/关键词） |
| 15 | DELETE | `/api/projects/{project_id}` | 删除项目（级联） |
| 16 | GET | `/api/projects/{project_id}/download` | 下载最终视频 |

### 1.3 资产（5）

| # | 方法 | 路径 | 说明 |
|:--:|:----:|:-----|:-----|
| 17 | POST | `/api/assets/upload` | 上传文件（multipart，配置限制） |
| 18 | GET | `/api/assets` | 资产列表（类型/关键词/分页） |
| 19 | PUT | `/api/assets/{id}` | 重命名资产（仅重命名） |
| 20 | DELETE | `/api/assets/{id}` | 删除资产（级联物理文件） |
| 21 | GET | `/upload/{path}` | 访问资产文件（打开/下载） |

### 1.4 教程（5）

| # | 方法 | 路径 | 说明 |
|:--:|:----:|:-----|:-----|
| 22 | GET | `/api/tutorials` | 教程列表 |
| 23 | GET | `/api/tutorials/{id}` | 教程详情（Markdown） |
| 24 | POST | `/api/tutorials` | 发布教程（直接发布） |
| 25 | PUT | `/api/tutorials/{id}` | 编辑教程 |
| 26 | DELETE | `/api/tutorials/{id}` | 删除教程 |

### 1.5 配置（2）

| # | 方法 | 路径 | 说明 |
|:--:|:----:|:-----|:-----|
| 27 | GET | `/api/settings` | 获取全部配置 |
| 28 | PUT | `/api/settings` | 保存配置（立即生效） |

### 1.6 系统与文件（3）

| # | 方法 | 路径 | 说明 |
|:--:|:----:|:-----|:-----|
| 29 | GET | `/api/system/status` | 系统健康检查 |
| 30 | GET | `/api/files/{path}` | 访问生成产物（图片/视频/音频） |

---

## 2. 通用约定

### 2.1 鉴权

- 请求头：`Authorization: Bearer <token>`（登录/初始化返回）；
- **免鉴权接口**：`GET /api/auth/status`、`POST /api/auth/setup`、`POST /api/auth/captcha`、`POST /api/auth/login`、`GET /api/system/status`；
- **开发期免鉴权（生成类）**：`/api/projects/*`、`/api/files/*`、`/upload/*`；
- **需鉴权**：`/api/users/*`、`/api/assets/*`、`/api/tutorials/*`、`/api/settings/*`、`POST /api/auth/logout`；
- token 有效期 **7 天**；修改密码/重置密码后旧 token 失效（401，需重新登录）。

### 2.2 错误码

| 状态码 | 含义 | 常见场景 |
|:------:|:-----|:---------|
| 200 | 成功 | 正常处理 |
| 400 | 请求错误 | 项目正在生成中（重复触发）、验证码错/过期、密码错、重命名改扩展名、上传超限/非法扩展名 |
| 401 | 未认证 | 未携带 token / token 失效（含改密后旧 token） |
| 403 | 禁止访问 | `/api/files`、`/upload` 路径穿越（`../`） |
| 404 | 资源不存在 | 项目/资产/教程/文件不存在 |
| 422 | 参数校验失败 | 请求体字段缺失或类型错误（Pydantic）、settings 数值/白名单校验失败 |
| 500 | 服务器错误 | 内部异常、LLM/ComfyUI 连接失败 |

错误响应格式：

```json
{ "code": 400, "message": "错误描述信息", "data": null }
```

> 注：FastAPI 标准 422 校验错误也可能返回 `{"detail": [...]}` 结构（Pydantic 原始错误），前端按两种结构兼容处理。

### 2.3 分页响应格式

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 12,
  "has_more": true
}
```

- 默认 `page=1`；项目列表 `page_size=12`、资产列表 `page_size=20`；
- 排序：`created_at DESC, id DESC`。

### 2.4 URL 构造规则

- 后端响应中所有图片/视频/音频/成片一律返回**可直接使用的 URL 字符串**，前端不自行拼路径；
- 产物：`/api/files/{path}`（如 `/api/files/proj_x/images/scene_001.png`）；
- 资产：`/upload/{path}`（如 `/upload/docs/方案.pdf`）；
- 成片下载：`/api/projects/{project_id}/download`。

### 2.5 敏感字段

- `GET /api/settings` 返回原始值 + `sensitive_keys` 列表（`llm_api_key` / `t2i_token` / `i2v_token` / `tts_password`）；
- 前端用密码框渲染（掩码 `******`）+ 显示/隐藏切换，明文只存在于当前会话内存。

---

## 3. 认证接口

### 3.1 查询初始化状态

```
GET /api/auth/status     （免鉴权）
```

**响应示例：**

```json
{ "need_setup": true }
```

| 字段 | 类型 | 说明 |
|:-----|:-----|:-----|
| `need_setup` | bool | `true` 表示管理员表为空，前端显示初始化面板；`false` 显示常规登录 |

### 3.2 初始化管理员

```
POST /api/auth/setup     （免鉴权，仅 need_setup=true 时可调用）
```

**请求体：**

```json
{
  "username": "admin",
  "password": "123456",
  "confirm": "123456"
}
```

**响应示例 — 200：**

```json
{
  "token": "api-key...",
  "user": { "id": 1, "username": "admin", "nickname": "", "avatar": "", "email": "", "created_at": "2026-08-20 10:00:00" }
}
```

**错误：** 400（已初始化/两次密码不一致/密码 <6 位）；422（字段缺失/类型错）。

> 创建即登录：直接返回 token，前端保存后进入工作台。

### 3.3 获取登录验证码

```
POST /api/auth/captcha   （免鉴权）
```

**响应示例：**

```json
{
  "captcha_id": "a1b2c3d4",
  "svg": "<svg xmlns=...>...</svg>"
}
```

| 字段 | 类型 | 说明 |
|:-----|:-----|:-----|
| `captcha_id` | string | 验证码 ID（登录时回传），一次性 |
| `svg` | string | SVG 图片内容（前端 `data:image/svg+xml` 渲染） |

> 6 位纯数字；有效期 120 秒；一次性（使用后失效）；登录失败自动刷新。

### 3.4 登录

```
POST /api/auth/login     （免鉴权）
```

**请求体：**

```json
{
  "username": "admin",
  "password": "123456",
  "captcha_id": "a1b2c3d4",
  "code": "483920"
}
```

**响应示例 — 200：**

```json
{
  "token": "api-key...",
  "user": { "id": 1, "username": "admin", "nickname": "", "avatar": "", "email": "", "created_at": "2026-08-20 10:00:00" }
}
```

**错误：**

```json
// 400 验证码错误或已过期
{ "code": 400, "message": "验证码错误或已过期", "data": null }
// 400 用户名或密码错误
{ "code": 400, "message": "用户名或密码错误", "data": null }
```

> 前端处理：登录失败 toast + 自动刷新验证码，**不清空用户名密码输入**。

### 3.5 登出

```
POST /api/auth/logout    （需鉴权，幂等宽松）
```

**响应示例：**

```json
{ "code": 0, "message": "已退出登录", "data": null }
```

> token 为无状态（服务端不存会话），前端清除 localStorage token 即可；401 全局拦截也会自动登出。

### 3.6 重置密码

```
POST /api/auth/reset-password   （免鉴权）
```

**请求体：**

```json
{
  "username": "admin",
  "new_password": "newpass123",
  "confirm": "newpass123"
}
```

**响应示例 — 200：**

```json
{ "code": 0, "message": "重置成功，请使用新密码登录", "data": null }
```

**错误：** 400（用户名不存在/两次不一致/密码过短）。

> 重置成功后 `password_version+1`，此前签发的所有 token 立即失效。

---

## 4. 用户接口

### 4.1 获取当前用户资料

```
GET /api/users/me        （需鉴权）
```

**响应示例：**

```json
{
  "id": 1,
  "username": "admin",
  "nickname": "管理员",
  "avatar": "",
  "email": "admin@example.com",
  "created_at": "2026-08-20 10:00:00"
}
```

### 4.2 修改用户资料

```
PUT /api/users/me        （需鉴权）
```

**请求体：**

```json
{ "nickname": "管理员", "avatar": "", "email": "admin@example.com" }
```

**响应示例：**

```json
{ "code": 0, "message": "已更新", "data": { "user": { "id": 1, "username": "admin", "nickname": "管理员", "avatar": "", "email": "admin@example.com", "created_at": "2026-08-20 10:00:00" } } }
```

### 4.3 修改密码

```
PUT /api/users/me/password   （需鉴权）
```

**请求体：**

```json
{
  "old_password": "123456",
  "new_password": "newpass123",
  "confirm": "newpass123"
}
```

**响应示例：**

```json
{ "code": 0, "message": "密码已修改，请重新登录", "data": null }
```

**错误：** 400（原密码错误/两次不一致）。

> 修改成功后 `password_version+1`，旧 token 立即失效（401）；前端主动清 token + toast「密码已修改，请重新登录」→ 回登录页。

---

## 5. 项目管理接口

### 5.1 创建项目

```
POST /api/projects      （开发期免鉴权）
```

**请求体：**

```json
{
  "name": "中国茶文化宣传片",
  "topic": "中国茶文化宣传片",
  "config": {
    "ratio": "16:9",
    "resolution": "高清720p",
    "fps": 16,
    "style": "写实",
    "voice": "none",
    "targetDuration": 30
  }
}
```

**请求体字段说明：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|:-----|:-----|:----:|:-------|:-----|
| `name` | string | ✅ | — | 项目名称 |
| `topic` | string | ✅ | — | 视频主题，AI 据此创作剧本 |
| `config.ratio` | string | ❌ | `"16:9"` | 视频比例：`"16:9"` / `"9:16"` / `"1:1"` |
| `config.resolution` | string | ❌ | `"普清360p"` | 分辨率等级（**只传等级，方向由比例补全**）：`普清360p` / `高清720p` / `超清1080p` |
| `config.fps` | int | ❌ | `16` | 帧率：16 / 24 / 30 |
| `config.style` | string | ❌ | `"写实"` | 画面风格：写实/动画/动漫/3D/赛博朋克/水墨风/像素风/油画风 |
| `config.voice` | string | ❌ | `"none"` | 配音音色：`none`（无配音）/ 温柔女声/明亮女声/浑厚男声/温暖男声/童声 |
| `config.targetDuration` | int | ❌ | `30` | 目标时长（秒），10~60 步长 5；分镜数 = 时长/5（限 3~12） |

> **分辨率说明：** 前端仅传等级；后端按比例补全方向写入 DB：`16:9 → 横屏`、`9:16 → 竖屏`、`1:1 → 横屏`。兼容旧值（如 `高清720p 横屏`）也会被正常解析。

**响应示例 — 200：**

```json
{ "project_id": "proj_20260825_103000", "status": "等待" }
```

**错误：** 422（字段缺失/类型错误）；400（非法分辨率等级/比例组合）。

### 5.2 开始生成视频

```
POST /api/projects/{project_id}/generate   （开发期免鉴权）
```

异步执行：立即返回，生成过程在后台线程中按序执行五步管线（剧本→[语音]→文生图→图生视频→合成）。

**路径参数：**

| 参数 | 类型 | 说明 |
|:-----|:-----|:-----|
| `project_id` | string | 项目 ID（来自创建接口） |

**响应示例 — 200：**

```json
{ "project_id": "proj_20260825_103000", "status": "started" }
```

**错误：**

```json
// 404 项目不存在
{ "code": 404, "message": "项目不存在", "data": null }
// 400 单并发冲突
{ "code": 400, "message": "当前已有项目正在创作中", "data": null }
```

> 前端处理：收到 400 单并发冲突时，创作页「开始创作」置灰 + 提供「查看进度」跳转到进行中项目详情。

### 5.3 查询生成状态

```
GET /api/projects/{project_id}/status   （开发期免鉴权）
```

**响应示例：**

```json
// 剧本创作阶段（等待态也返回 step/progress）
{ "status": "等待", "current_step": "script", "progress_percent": 5, "error_msg": "" }

// 生成中（有配音路径）
{ "status": "进行中", "current_step": "voice", "progress_percent": 20, "error_msg": "" }

// 生成完成
{ "status": "完成", "current_step": "done", "progress_percent": 100, "error_msg": "" }

// 生成失败
{ "status": "失败", "current_step": "error", "progress_percent": 0, "error_msg": "ComfyUI 连接超时" }
```

**字段说明：**

| 字段 | 类型 | 说明 |
|:-----|:-----|:-----|
| `status` | string | `等待` / `进行中` / `完成` / `失败`（以 DB 为准） |
| `current_step` | string | `script` / `voice` / `images` / `videos` / `compose` / `done` / `error`（顺序） |
| `progress_percent` | int | 整体进度百分比（0-100） |
| `error_msg` | string | 错误信息（仅失败时返回） |

**生成步骤与进度对照：**

| 步骤 | 进度点 | 说明 |
|:-----|:------:|:-----|
| `script` | 5% | AI 创作剧本（ScriptWriter） |
| `voice` | 20% | 语音合成配音（VoiceActor，voice=none 时跳过） |
| `images` | 35% | 文生图生成分镜图片（ImageCreator） |
| `videos` | 60% | 图生视频生成分镜片段（VideoCreator） |
| `compose` | 85% | FFmpeg 合成最终视频（VideoComposer） |
| `done` | 100% | 生成完成 |

> **分镜级实时写库：** 生成过程中 GET 项目详情即可实时看到已完成分镜的图片/视频/语音，无需等待整个阶段。

### 5.4 获取项目详情

```
GET /api/projects/{project_id}   （开发期免鉴权）
```

**响应示例：**

```json
{
  "project_id": "proj_20260825_103000",
  "name": "中国茶文化宣传片",
  "topic": "中国茶文化宣传片",
  "config": {
    "ratio": "16:9",
    "resolution": "高清720p 横屏",
    "fps": 16,
    "style": "写实",
    "voice": "none",
    "target_duration": 30,
    "scene_count": 6
  },
  "cover_url": "/api/files/proj_20260825_103000/images/scene_001.png",
  "status": "完成",
  "error_msg": "",
  "final_video_url": "/api/files/proj_20260825_103000/final/proj_20260825_103000.mp4",
  "download_url": "/api/projects/proj_20260825_103000/download",
  "scenes": [
    {
      "scene_no": 1,
      "duration": 5,
      "description": "清晨茶园，薄雾缭绕，茶农正在采摘嫩芽",
      "narration": "清晨的第一缕阳光洒在茶园里，嫩绿的茶芽上还挂着露珠。",
      "subtitle": "清晨的第一缕阳光洒在茶园里，嫩绿的茶芽上还挂着露珠。",
      "t2i_prompt": "A misty tea plantation at dawn, farmers picking fresh tea leaves, realistic style",
      "i2v_prompt": "gentle camera pan across tea field, morning mist moving, cinematic",
      "camera": "中景",
      "image_url": "/api/files/proj_20260825_103000/images/scene_001.png",
      "video_url": "/api/files/proj_20260825_103000/videos/scene_001.mp4",
      "voice_path": "proj_20260825_103000/audio/scene_001.wav",
      "voice_duration": 4.82,
      "status": "完成"
    }
  ],
  "created_at": "2026-08-25T10:30:00"
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|:-----|:-----|:-----|
| `project_id` | string | 项目 ID |
| `config` | object | 视频配置（快照解析，含补全后的 resolution） |
| `cover_url` | string | 封面 URL（= 第 1 分镜 image_url，无则空） |
| `status` | string | 等待/进行中/完成/失败 |
| `final_video_url` | string | 成片 URL（完成时有值） |
| `download_url` | string | 成片下载 URL |
| `scenes[]` | array | 分镜列表（image_url/video_url 可直接用于 img/video src） |
| `scenes[].voice_duration` | float | 分镜语音真实时长（秒，驱动视频时长） |

### 5.5 项目列表

```
GET /api/projects?page=1&page_size=12&status=完成&keyword=茶   （开发期免鉴权）
```

**查询参数：**

| 参数 | 类型 | 说明 |
|:-----|:-----|:-----|
| `page` | int | 页码，默认 1 |
| `page_size` | int | 每页数量，默认 12 |
| `status` | string | 状态筛选（等待/进行中/完成/失败，可选） |
| `keyword` | string | 关键词（匹配 name/topic，可选） |

**响应示例：**

```json
{
  "items": [
    {
      "project_id": "proj_20260825_103000",
      "name": "中国茶文化宣传片",
      "topic": "中国茶文化宣传片",
      "cover_url": "/api/files/proj_20260825_103000/images/scene_001.png",
      "status": "完成",
      "scene_count": 6,
      "created_at": "2026-08-25 10:30:00"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 12,
  "has_more": false
}
```

### 5.6 删除项目

```
DELETE /api/projects/{project_id}   （开发期免鉴权）
```

**响应示例：**

```json
{ "code": 0, "message": "已删除", "data": { "freed_mb": 128.5 } }
```

**说明：**
- 级联删除：projects 行 + 全部 scenes 行 + `output/{project_id}/` 整目录；
- `freed_mb` = 目录内文件总字节 / (1024*1024)，保留 1 位小数（仅预估展示）；
- 前端弹窗展示「将删除 1 个项目，释放约 X MB，不可恢复」，用户确认后调用；
- 错误：404（项目不存在）；400（project_id 格式非法）。

### 5.7 下载最终视频

```
GET /api/projects/{project_id}/download   （开发期免鉴权）
```

- **成功：** 返回 MP4 文件流（`Content-Type: video/mp4`，`Content-Disposition: attachment; filename="项目名.mp4"`）；
- **404：** 视频未生成或文件不存在。

```json
{ "code": 404, "message": "视频未生成", "data": null }
```

---

## 6. 资产接口

### 6.1 上传文件

```
POST /api/assets/upload   （需鉴权，multipart/form-data）
```

**请求：** 表单字段 `files`（支持多文件，字段名 `files`，可重复）。

**限制（读 settings 配置）：**

| 规则 | 值（默认） |
|:-----|:-----------|
| 文档/图片大小上限 | `upload_doc_img_limit_mb`（默认 10MB） |
| 音视频大小上限 | `upload_media_limit_mb`（默认 30MB） |
| 扩展名白名单 | `upload_allow_ext`（pdf,docx,xlsx,pptx,txt,md,png,jpg,jpeg,webp,gif,mp3,wav,m4a,mp4,webm,mov） |
| 存储目录 | 按类型：`upload/docs`、`upload/images`、`upload/media` |

**响应示例：**

```json
{
  "items": [
    { "id": 1, "file_name": "方案.pdf", "file_type": "文档", "ext": "pdf", "file_size": 204800, "file_path": "upload/docs/方案.pdf", "url": "/upload/docs/方案.pdf" },
    { "id": 2, "file_name": "素材.png", "file_type": "图片", "ext": "png", "file_size": 512000, "file_path": "upload/images/素材.png", "url": "/upload/images/素材.png" }
  ],
  "failed": [
    { "file_name": "超大视频.mp4", "reason": "文件大小超过限制(30MB)" }
  ]
}
```

> 部分成功：成功项返回 `items`，失败项返回 `failed`（含文件名 + 原因）；任一文件超限/非法扩展名 → 该文件失败，不影响其他文件。文件名冲突自动追加 `(1)`、`(2)`。

### 6.2 资产列表

```
GET /api/assets?type=图片&keyword=素材&page=1&page_size=20   （需鉴权）
```

**查询参数：**

| 参数 | 类型 | 说明 |
|:-----|:-----|:-----|
| `type` | string | 类型筛选：`文档` / `图片` / `音视频` / `全部`（默认全部） |
| `keyword` | string | 关键词（匹配 file_name） |
| `page` / `page_size` | int | 分页，page_size 默认 20 |

**响应示例：**

```json
{
  "items": [
    { "id": 1, "file_name": "方案.pdf", "file_type": "文档", "ext": "pdf", "file_size": 204800, "file_path": "upload/docs/方案.pdf", "url": "/upload/docs/方案.pdf", "created_at": "2026-08-25 09:00:00" }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

### 6.3 重命名资产（仅重命名）

```
PUT /api/assets/{id}   （需鉴权）
```

**请求体：**

```json
{ "file_name": "方案-终版" }
```

**响应示例：**

```json
{ "code": 0, "message": "已重命名", "data": { "id": 1, "file_name": "方案-终版.pdf", "file_path": "upload/docs/方案-终版.pdf", "url": "/upload/docs/方案-终版.pdf" } }
```

**说明：** 保留原扩展名（新名无扩展名自动补）；扩展名不同 → 400「不能修改扩展名」；物理文件与 DB file_path 同步重命名。

### 6.4 删除资产

```
DELETE /api/assets/{id}   （需鉴权）
```

**响应示例：**

```json
{ "code": 0, "message": "已删除", "data": { "freed_mb": 0.2 } }
```

> 级联删除：assets 行 + `upload/{type}/{file}` 物理文件；物理删除失败时 message 追加「物理文件删除失败，请手动清理」+ `warn` 字段。

### 6.5 访问资产文件

```
GET /upload/{path}   （开发期免鉴权，path 为相对 upload/ 的路径）
```

- 示例：`GET /upload/docs/方案.pdf` → 返回文件流（浏览器决定打开或下载）；
- **403：** 非法路径（含 `../` 路径穿越）；
- **404：** 文件不存在。

---

## 7. 教程接口

### 7.1 教程列表

```
GET /api/tutorials?tag=项目文档   （需鉴权）
```

**响应示例：**

```json
{
  "items": [
    { "id": 1, "title": "需求文档", "summary": "视频智造平台 — 需求文档...", "tags": "项目文档", "cover": "", "created_at": "2026-08-25 10:00:00", "updated_at": "2026-08-25 10:00:00" }
  ]
}
```

> 列表不含 content；排序 `sort_order ASC, id DESC`；教程数据量小不分页。

### 7.2 教程详情

```
GET /api/tutorials/{id}   （需鉴权）
```

**响应示例：**

```json
{
  "id": 1,
  "title": "需求文档",
  "summary": "视频智造平台 — 需求文档...",
  "tags": "项目文档",
  "cover": "",
  "content": "# 视频智造平台 — 需求文档\n\n...Markdown 原文...",
  "is_published": 1,
  "created_at": "2026-08-25 10:00:00",
  "updated_at": "2026-08-25 10:00:00"
}
```

### 7.3 发布教程

```
POST /api/tutorials   （需鉴权）
```

**请求体：**

```json
{
  "title": "平台使用指南",
  "summary": "快速上手视频创作",
  "tags": "使用指南",
  "cover": "",
  "content": "# 平台使用指南\n\n## 第一步...\n"
}
```

**响应示例：**

```json
{ "code": 0, "message": "已发布", "data": { "id": 3 } }
```

> **直接发布无草稿态**：is_published 恒 1，保存即上线。

### 7.4 编辑教程

```
PUT /api/tutorials/{id}   （需鉴权）
```

**请求体：** 同发布（title/summary/tags/cover/content），可部分更新。保存即时生效。

### 7.5 删除教程

```
DELETE /api/tutorials/{id}   （需鉴权）
```

**响应示例：**

```json
{ "code": 0, "message": "已删除", "data": null }
```

> 仅删 tutorials 行，无物理文件。**注意：** 若教程表被清空，重启后会自动重新导入 doc/*.md（设计行为）。

---

## 8. 配置接口

### 8.1 获取全部配置

```
GET /api/settings   （需鉴权）
```

**响应示例：**

```json
{
  "settings": {
    "llm_api_base": "http://127.0.0.1:1234/v1",
    "llm_api_key": "sk-xxxxxxxx",
    "llm_model": "qwen3.8-27b",
    "t2i_url": "https://127.0.0.1:8080",
    "t2i_token": "xxxx",
    "t2i_timeout": "300",
    "t2i_poll_interval": "5",
    "i2v_url": "https://127.0.0.1:8080",
    "i2v_token": "xxxx",
    "i2v_timeout": "300",
    "i2v_poll_interval": "10",
    "tts_base_url": "https://127.0.0.1:7860",
    "tts_username": "admin",
    "tts_password": "xxxx",
    "upload_doc_img_limit_mb": "10",
    "upload_media_limit_mb": "30",
    "upload_allow_ext": "pdf,docx,xlsx,pptx,txt,md,png,jpg,jpeg,webp,gif,mp3,wav,m4a,mp4,webm,mov"
  },
  "sensitive_keys": ["llm_api_key", "t2i_token", "i2v_token", "tts_password"]
}
```

> 敏感字段返回原始值，由前端控制显隐（SensitiveInput 掩码 `******` + 显示切换）；明文不写日志。

### 8.2 保存配置

```
PUT /api/settings   （需鉴权）
```

**请求体：**

```json
{
  "settings": {
    "llm_api_base": "http://127.0.0.1:1234/v1",
    "llm_api_key": "sk-xxxxxxxx",
    "t2i_timeout": "300",
    "upload_doc_img_limit_mb": "10",
    "upload_allow_ext": "pdf,docx,xlsx,pptx,txt,md,png,jpg,jpeg,webp,gif,mp3,wav,m4a,mp4,webm,mov"
  }
}
```

**响应示例：**

```json
{ "code": 0, "message": "保存成功，已生效", "data": null }
```

**校验规则（422）：**

| 字段 | 规则 |
|:----|:-----|
| t2i_timeout / t2i_poll_interval / i2v_timeout / i2v_poll_interval / upload_doc_img_limit_mb / upload_media_limit_mb | 必须为数字且 >0 |
| upload_allow_ext | 非空、逗号分隔 |

> **保存立即生效**：写 settings 表 + 刷新后端内存缓存；生成管线下次调用即用新参数（进行中任务按创建时快照执行）；资产上传限制即时生效。**无「恢复默认」按钮**。

---

## 9. 系统状态与文件服务

### 9.1 查询系统状态

```
GET /api/system/status   （免鉴权）
```

**响应示例 — 成功：**

```json
{
  "status": "ok",
  "gpu": "NVIDIA GeForce RTX 3060",
  "vram_free_mb": 10240,
  "vram_total_mb": 12288,
  "comfyui_version": "0.3.15"
}
```

**响应示例 — 失败：**

```json
{ "status": "error", "detail": "无法连接到 ComfyUI 服务器" }
```

> 通过 ComfyUI 文生图服务的 system_stats 探测；前端工作台侧栏「系统状态」小字使用。

### 9.2 获取生成产物文件

```
GET /api/files/{path}   （开发期免鉴权，path 为相对 output/ 的路径）
```

- 示例：`GET /api/files/proj_xxx/images/scene_001.png`；
- **403：** 非法路径（`../` 路径穿越，resolve + is_relative_to 校验）；
- **404：** 文件不存在。

---

## 10. 前端调用示例

### 10.1 完整创作流程（fetch 版）

```javascript
// 1. 初始化判定（首次部署）
const status = await (await fetch('http://localhost:8000/api/auth/status')).json();
if (status.need_setup) {
  // 初始化面板（无验证码，创建即登录）
  const setup = await fetch('http://localhost:8000/api/auth/setup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: '123456', confirm: '123456' })
  }).then(r => r.json());
  localStorage.setItem('token', setup.token);
} else {
  // 常规登录：先取验证码，再登录
  const cap = await fetch('http://localhost:8000/api/auth/captcha', { method: 'POST' }).then(r => r.json());
  // 渲染 cap.svg 到 <img src="data:image/svg+xml;base64,...">
  const login = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'admin', password: '123456', captcha_id: cap.captcha_id, code: '483920' })
  }).then(r => r.json());
  localStorage.setItem('token', login.token);
}

const authHeaders = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('token')}` };

// 2. 创建项目（voice=none 无配音）
const proj = await fetch('http://localhost:8000/api/projects', {
  method: 'POST',
  headers: authHeaders,
  body: JSON.stringify({
    name: '中国茶文化宣传片',
    topic: '中国茶文化宣传片',
    config: { ratio: '16:9', resolution: '高清720p', fps: 16, style: '写实', voice: 'none', targetDuration: 30 }
  })
}).then(r => r.json());
const projectId = proj.project_id;

// 3. 开始生成（异步）
await fetch(`http://localhost:8000/api/projects/${projectId}/generate`, { method: 'POST', headers: authHeaders });

// 4. 轮询状态（每 3 秒）
const interval = setInterval(async () => {
  const s = await fetch(`http://localhost:8000/api/projects/${projectId}/status`).then(r => r.json());
  if (s.status === '完成') {
    clearInterval(interval);
    const detail = await fetch(`http://localhost:8000/api/projects/${projectId}`).then(r => r.json());
    // 播放: detail.final_video_url  下载: detail.download_url
  } else if (s.status === '失败') {
    clearInterval(interval);
    console.error('生成失败:', s.error_msg);
  } else {
    updateProgress(s.progress_percent, s.current_step);   // script/voice/images/videos/compose
  }
}, 3000);
```

### 10.2 Axios 封装版本（项目实际使用结构）

```typescript
// src/api/http.ts
import axios from 'axios'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 30000
})

http.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use（res => res.data,                              // 成功直接返回数据体
  err => {
    if (err.response?.status === 401) {          // 401 全局登出
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }）

// src/api/projects.ts
export const createProject = (data: any) => http.post('/projects', data)
export const startGeneration = (id: string) => http.post(`/projects/${id}/generate`)
export const getStatus = (id: string) => http.get(`/projects/${id}/status`)
export const getProject = (id: string) => http.get(`/projects/${id}`)
export const listProjects = (params: any) => http.get('/projects', { params })
export const deleteProject = (id: string) => http.delete(`/projects/${id}`)
export const getDownloadUrl = (id: string) => `${API_BASE}/api/projects/${id}/download`

// src/api/auth.ts
export const getAuthStatus = () => http.get('/auth/status')
export const setupAdmin = (data: any) => http.post('/auth/setup', data)
export const getCaptcha = () => http.post('/auth/captcha')
export const login = (data: any) => http.post('/auth/login', data)
export const logout = () => http.post('/auth/logout')
export const resetPassword = (data: any) => http.post('/auth/reset-password', data)
export const getMe = () => http.get('/users/me')
export const updateMe = (data: any) => http.put('/users/me', data)
export const changePassword = (data: any) => http.put('/users/me/password', data)

// src/api/assets.ts / tutorials.ts / settings.ts（按需封装 upload/list/rename/delete、CRUD、GET/PUT）
```

---

## 11. 接口变更记录

| 版本 | 日期 | 变更内容 |
|:----|:-----|:---------|
| v2.0 | 2026-08-25 | 新增认证 9 接口 + 用户 3 接口；新增资产 5 接口、教程 5 接口、配置 2 接口；项目接口响应字段更新（cover_url/final_video_url/download_url）；错误码统一 `{code,message,data}`；创建项目 `config.voice` 默认值改为 `none`（无配音）、`config.resolution` 只传等级（方向由比例补全）；状态接口 `current_step` 顺序 script→voice→images→videos→compose；进度点更新（voice=20/images=35/videos=60）；详情响应增加 `voice_duration` |

---

> **文档维护：** 本文档随接口变更持续更新。
> **相关文档：** 需求文档.md / 系统架构说明文档.md / 系统开发手册.md / 项目基本情况说明.md
