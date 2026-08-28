# Linux 服务器部署手册（aivideo_v2 / 视频智造平台 V2.0）

> 适用环境：CentOS 7.9 + 宝塔面板（BT）
> 文档版本：2026-08-28
> 本文涵盖从零部署到上线，以及部署过程中已踩坑的全部报错与解决方案。
> ⚠️ 示例声明：本文档中的路径（如 `/home/aivideo_v2_backend`、`/www/wwwroot/aivideo`、`/www/server/pyporject_evn/...`）、域名（`你的域名`）、端口、venv 名称等均为**占位示例**，请按你实际部署环境替换；文档不内置任何真实账号与密码，请使用你自己的环境账号。

---

## 一、部署架构总览

**不拆分两个对外站点**，采用「单对外站点 + Nginx 反向代理」方案：

```
浏览器 / 客户端
      │
      ▼
宝塔 Nginx 站点（域名 你的域名）
      │  静态文件直接返回（前端 dist）
      │  仅以下前缀反代到后端：
      │    /api     → 127.0.0.1:8000   （所有接口）
      │    /upload  → 127.0.0.1:8000   （文件上传）
      │    /static  → 127.0.0.1:8000   （后端生成产物：视频/音频）
      │    /docs /openapi.json → 127.0.0.1:8000 （API 文档，可选）
      ▼
FastAPI 后端（gunicorn + UvicornWorker，仅监听 127.0.0.1:8000，不暴露公网）
```

**端口约定**
- 对外仅开 80 / 443（+ 22 SSH）；8000 端口不对外。
- 后端绑定 `127.0.0.1:8000`（只对内网反代开放）。
- 访问入口：
  - 前端页面：`http://你的域名`（或服务器 IP）
  - API 文档：`http://你的域名/docs`
  - 后端直连（仅调试）：`http://127.0.0.1:8000`

**最终生产配置**
- 后端：`gunicorn` + `worker_class = 'uvicorn.workers.UvicornWorker'` + `workers = 1`
- 前端：静态站点 + Nginx 反代

---

## 二、环境准备（CentOS 7 关键坑）

### 2.1 Python
- CentOS 7 自带 Python 2.7，太旧，**不可用于本项目**。
- 用**宝塔「Python 项目管理器」插件**安装 Python 3.10+（插件自带编译好的运行时，避免手动编译 OpenSSL 坑）。
- 本项目 `requirements.txt` 含 `fastapi 0.138`、`uvicorn 0.49`、`starlette`、`pydantic` 等，**不含 gunicorn**（gunicorn 由宝塔管理器自带，无需手动装）。

### 2.2 FFmpeg（必装）
- CentOS 7 官方源无 ffmpeg。下载 Linux 静态版（johnvansickle.com 的 ffmpeg 静态构建）。
- 将 `ffmpeg`、`ffprobe` 放到 `/usr/local/bin/` 并加执行权限，或加入 `PATH`。
- ⚠️ 代码只认系统命令名 `ffmpeg`，**不要**把 Windows 的 `ffmpeg.exe` 放进 `video-platform/bin/`（那是 Windows 专用）。

### 2.3 Node.js（仅本机构建前端用，服务器无需安装）
- 前端在本机（Windows / macOS）执行 `npm run build` 产出 `dist/`，再上传 `dist/` 即可，服务器不需要 Node。

### 2.4 外部 AI 服务（本机或远程）
- 默认地址：Qwen `127.0.0.1:1234`、ComfyUI `127.0.0.1:8080`、IndexTTS `127.0.0.1:7860`。
- 若这些服务在别的机器，登录后到「系统设置」页改为远程地址并测试连通性。

---

## 三、文件上传

### 3.1 后端
上传后端整包到服务器，例如 `/home/aivideo_v2_backend/`：
```
/home/aivideo_v2_backend/
├── main.py                # 后端入口，app 对象名 = app（gunicorn 用 main:app）
├── requirements.txt
├── video-platform/        # 后端代码（services/、api/）
├── static/                # 音色参考音频 static/speaker/*.mp3（随项目分发）
├── doc/                   # 教程文档（*.md），启动时会导入 tutorials 表
├── output/               # 空目录，生成产物落盘（需可写）
├── upload/               # 空目录，上传资产（需可写）
└── sqlite/               # 空目录，数据库 aivideo.db 落盘（需可写）
```
> ⚠️ `doc/` 目录请用**二进制模式**上传（宝塔文件管理、或 `scp`/`rsync`），不要用文本模式，否则可能被转码污染导致启动报错（见第六章 故障 3）。

### 3.2 前端
- 本机：`cd video-frontend && npm install && npm run build` → 产出 `dist/`。
- 上传 `dist/` 全部内容到宝塔站点根目录，例如 `/www/wwwroot/aivideo/`。

---

## 四、后端部署（宝塔 Python 项目）

### 4.1 安装依赖
在宝塔创建的 venv 中安装依赖（首次）：
```bash
/www/server/pyporject_evn/aivideo_v2_backend_venv/bin/pip install -r /home/aivideo_v2_backend/requirements.txt
```

### 4.2 项目配置
宝塔 → Python 项目管理器 → 添加 / 编辑项目：
```
项目目录 (chdir) : /home/aivideo_v2_backend
启动方式         : gunicorn
应用对象         : main:app
监听地址 (bind)  : 127.0.0.1:8000
启动用户         : www
worker_class     : uvicorn.workers.UvicornWorker
workers          : 1
threads          : 2（可选）
pidfile          : /home/aivideo_v2_backend/gunicorn.pid
accesslog        : /www/wwwlogs/python/aivideo_v2_backend/gunicorn_acess.log
errorlog         : /www/wwwlogs/python/aivideo_v2_backend/gunicorn_error.log
loglevel         : info
```
勾选「开机启动 / 自动重启」保活。

> **关键两行**（缺了就会报第六章故障 1/2）：
> ```
> worker_class = 'uvicorn.workers.UvicornWorker'
> workers = 1
> ```

### 4.3 目录写权限
`output/`、`upload/`、`sqlite/` 需宝塔运行用户（www）可写，否则生成视频/上传会失败：
```bash
chown -R www:www /home/aivideo_v2_backend/output /home/aivideo_v2_backend/upload /home/aivideo_v2_backend/sqlite
# 或至少给 755 / 777
```

---

## 五、前端站点 + 反向代理

### 5.1 添加站点
宝塔 → 网站 → 添加站点：域名填你的域名（或服务器 IP），根目录 `/www/wwwroot/aivideo`，纯静态即可。

### 5.2 伪静态（SPA 路由回退）
前端用 `history` 模式（`createWebHistory`），刷新子路由会 404，必须加：
```
try_files $uri $uri/ /index.html;
```

### 5.3 反向代理（最关键，决定验证码/接口能否用）
**用「反向代理」（proxy_pass），不要用「重定向」（rewrite permanent）！**
详情见第六章故障 5。

宝塔 → 网站 → 反向代理 → 添加，或在站点「配置文件」`server {}` 内手加：
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /upload/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /static/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```
> ⚠️ `proxy_pass` 后面**不要**带 `/api`（写成 `http://127.0.0.1:8000` 不带路径），这样 `/api/auth/captcha` 原样转发到后端，路径才对得上。

### 5.4 HTTPS / 防火墙
- 宝塔安全 → 放行 80、443；**不要**放行 8000。
- 有域名就在站点「SSL」一键申请 Let's Encrypt（建议强制 HTTPS）。无域名用 IP 访问即可。

---

## 六、已踩坑报错与解决方案（重点）

### 故障 1：uWSGI 启动 FastAPI 报 `FastAPI.__call__() missing 1 required positional argument: 'send'`
- **现象**：`curl http://127.0.0.1:8000` 返回 `Empty reply from server`（curl 52）；日志报 `TypeError: FastAPI.__call__() missing 1 required positional argument: 'send'`。
- **根因**：FastAPI 是 **ASGI** 应用（调用签名 `async def __call__(self, scope, receive, send)`）。宝塔若用 **uWSGI 的 HTTP/WSGI 模式**把它当 **WSGI** 应用启动（按 `app(environ, start_response)` 调用，只传 2 个参数），第三个 `send` 缺失 → 直接 500 且无响应体。
- **解决**：**放弃 uWSGI**，改用 gunicorn + UvicornWorker（见第四章）。不要用 uWSGI 启动 FastAPI。

### 故障 2：Gunicorn 默认 `worker_class='sync'` 报 `Internal Server Error`
- **现象**：`curl` 返回 HTML 页面 `<title>Internal Server Error</title>`。
- **根因**：gunicorn 默认 `sync` worker 是 **WSGI** 协议，同样调不动 FastAPI（ASGI）。
- **解决**：把配置 `worker_class = 'sync'` 改为：
  ```
  worker_class = 'uvicorn.workers.UvicornWorker'
  ```
  改完日志应出现 `Using worker: uvicorn.workers.UvicornWorker`，应用进入 lifespan 启动钩子。

### 故障 3：启动钩子导入 doc 报 `UnicodeEncodeError: '\udcb6' surrogates not allowed`
- **现象**：worker 启动后 `Application startup failed`，日志定位到 `db.py` 的 `import_docs_if_empty` → `insert_tutorial` → `UnicodeEncodeError: 'utf-8' codec can't encode character '\udcb6' ...`。
- **根因**：启动时 `import_docs_if_empty` 会扫描 `doc/*.md` 写入 `tutorials` 表。服务器上的某份 `doc/*.md` 文件含**非法代理对字符 `\udcb6`**（典型转码事故：一个字节 `0xB6` 被当 surrogateescape 解码成代理对）。SQLite 用 UTF-8 存储，这种字符写不进去 → 启动直接崩。
- **解决**：
  1. **代码侧（已修复并保留）**：`db.py` 的 `import_docs_if_empty` 改为读文件用 `errors="replace"`，导入前用列表推导剔除 `0xD800–0xDFFF` 代理对字符，并把单篇 `insert_tutorial` 包 try/except（单篇失败只跳过，不中断整体导入）；`insert_tutorial` 对所有字段做兜底清洗。
  2. **数据侧**：若导入在崩前已落了部分数据，需先清空再重导：
     ```bash
     # 方式 A：用 venv python（必定带 sqlite3，无需装系统客户端）
     /www/server/pyporject_evn/aivideo_v2_backend_venv/bin/python -c \
     "import sqlite3; c=sqlite3.connect('/home/aivideo_v2_backend/sqlite/aivideo.db'); c.execute('DELETE FROM tutorials'); c.commit(); print('cleared')"
     # 方式 B：装系统 sqlite 客户端
     yum install -y sqlite
     sqlite3 /home/aivideo_v2_backend/sqlite/aivideo.db "DELETE FROM tutorials;"
     ```
  3. **治本**：用**二进制模式**重新上传 `doc/` 目录，消除转码污染。
- **验证**：重启后日志应出现 `[startup] 已导入 5 篇教程文档`（确认 5 篇全齐）。

### 故障 4：验证码接口 `curl` 返回 `{"detail":"Not Found"}`
- **现象**：`curl http://127.0.0.1:8000/auth/captcha` → `{"detail":"Not Found"}`，但 `/docs` 能正常打开（说明后端本身没问题）。
- **根因**：URL 写错了。真实路由是 **`POST /api/auth/captcha`**：
  - 路由前缀 `/api/auth`（`auth_routes.py`）
  - 端点是 `@router.post("/captcha")` → **POST 方法**，不是 GET
  - 挂在 `/api` 前缀下，不是根 `/auth`
- **正确测试命令**：
  ```bash
  curl -s -X POST http://127.0.0.1:8000/api/auth/captcha
  # 正常返回：{"captcha_id":"...","svg":"<svg ...>...</svg>"}
  ```

### 故障 5：网站验证码不显示 / DevTools 请求跳到 `127.0.0.1`
- **现象**：浏览器登录页无验证码；DevTools 里请求直接打到 `http://127.0.0.1:8000/auth/captcha`（内网地址，浏览器访问不到）。
- **根因**：前端站点误配成了**重定向（301）**而非**反向代理**：
  ```nginx
  # ❌ 错误：让浏览器跳走（rewrite permanent）
  rewrite ^/api(.*) http://127.0.0.1:8000$1 permanent;
  ```
  这条规则把 `/api/xxx` 永久重定向到 `127.0.0.1:8000/xxx`（且 `$1` 吃掉了 `/api` 前缀），浏览器照做 → 打到内网地址失败。
- **解决**：
  1. 删除「重定向」面板里那条 `/api → 127.0.0.1:8000` 规则。
  2. 改用**反向代理**（`proxy_pass`，Nginx 在服务端转发，浏览器无感知）：
     ```nginx
     location /api/ {
         proxy_pass http://127.0.0.1:8000;
         proxy_set_header Host $host;
     }
     ```
  3. 重载 Nginx（宝塔「重载配置」或 `nginx -s reload`）。

| 你之前写的 | 应该写的 |
|---|---|
| `rewrite ... permanent;`（让浏览器跳走） | `proxy_pass ...;`（Nginx 服务端转发） |
| 「重定向」功能 | 「反向代理」功能 |

### 故障 6：验证码偶发「错误或已过期」（`{"code":400,"message":"验证码错误或已过期"}`）
- **现象**：输入正确验证码，有时通过、有时报错；多刷新几次不稳定。
- **根因**：Gunicorn `workers=4` 是 4 个独立 Python 进程，验证码存在模块级全局变量 `_captchas: Dict` 里，**每个 worker 各有一份、互不共享**：
  ```
  打开登录页 → 请求打到 Worker-A → POST /captcha → 写入 Worker-A 内存
  输入验证码登录 → 请求打到 Worker-B → POST /login → 在 Worker-B 内存找不到 → 报错
  ```
  恰好轮到同一 worker 就正常，打到别的就失败。
  > 同理，token 签名密钥 `_SECRET` 也是每个进程启动时随机生成，多 worker 时登录（A 签发）后后续请求打到 B → 验签失败 → 偶发 401。
- **解决（本站最终采用）**：本站点内部使用、无并发，直接把 `workers = 4` 改为 `workers = 1`：
  ```
  workers = 1
  ```
  单进程 = 一份内存 = 验证码永远一致；同时顺带消除 token 密钥不一致导致的偶发 401。
  - 若未来要对外/上量，应改用 SQLite 持久化验证码（多 worker 共享同一库文件），但当前内部站点 `workers=1` 最省事稳妥。

---

## 七、验证清单（上线前逐项确认）

**后端（服务器本机）**
```bash
# 1. 健康检查（免鉴权）
curl http://127.0.0.1:8000/api/system/status
# 2. 验证码接口（注意 POST + /api 前缀）
curl -s -X POST http://127.0.0.1:8000/api/auth/captcha
# 3. API 文档
curl http://127.0.0.1:8000/docs
```

**经反代（外网地址）**
```bash
curl -s -X POST http://你的域名/api/auth/captcha
# 返回 JSON 即反代生效
```

**浏览器**
- 打开 `http://你的域名/login`，验证码应正常显示。
- 多次刷新、多次登录，验证码应 100% 稳定通过（不再偶发 400）。
- 用你自己的测试账号登录成功，进入工作台（文档不内置任何账号，请使用实际环境的账号密码；该步骤仅为示例验证项）。

---

## 八、升级 / 重新发布流程

以后更新代码，只需：

1. **后端**：替换 `/home/aivideo_v2_backend` 下对应文件；若 `requirements.txt` 有新增依赖，重新 `pip install -r requirements.txt`；宝塔重启 Python 项目。
2. **前端**：本机重新 `npm run build` 产出 `dist/`，覆盖上传到站点根目录（无需重启 Nginx，除非改了反代配置）。
3. **doc 目录**：用二进制模式上传，避免再次转码污染。
4. 重启后按第七章验证清单走一遍。

---

## 九、快速排查速查表

| 报错 / 现象 | 根因 | 关键修复 |
|---|---|---|
| `FastAPI.__call__() missing 1 required positional argument: 'send'` + curl 52 空响应 | uWSGI 用 WSGI 模式调 ASGI | 弃用 uWSGI，改用 gunicorn |
| `Internal Server Error`（gunicorn 500 页） | `worker_class='sync'`（WSGI） | 改 `worker_class='uvicorn.workers.UvicornWorker'` |
| `UnicodeEncodeError: '\udcb6' surrogates not allowed` 启动崩 | doc/*.md 含代理对字符，SQLite 写不进 | db.py 清洗代码 + 清空 tutorials 表 + 二进制重传 doc/ |
| `/auth/captcha` 返回 `{"detail":"Not Found"}` | 真实路由是 `POST /api/auth/captcha` | 用正确的 URL + POST 方法测试 |
| 网站验证码不显示，请求跳 `127.0.0.1` | 误配 301 重定向而非反代 | 删重定向，加 `location /api/ { proxy_pass ... }` |
| 验证码偶发「错误或已过期」 | workers=4 内存不同步 | `workers = 1` |
