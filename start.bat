@echo off
chcp 65001 >nul
echo ============================================
echo  本地视频智造平台 - 一键启动
echo ============================================
echo.

REM 当前目录即为项目根目录
set ROOT=%~dp0

REM 检查前端依赖（以 vite 可执行为准，避免残缺 node_modules 被跳过安装）
if not exist "%ROOT%video-frontend\node_modules\.bin\vite.cmd" (
    echo [1/3] 安装前端依赖...
    cd /d "%ROOT%video-frontend"
    call npm install
    if errorlevel 1 (
        echo.
        echo  [错误] 前端依赖安装失败！
        echo  请手动执行: cd /d "%ROOT%video-frontend" ^&^& npm install
        pause
        exit /b 1
    )
    if not exist "%ROOT%video-frontend\node_modules\.bin\vite.cmd" (
        echo.
        echo  [错误] 依赖安装后 vite 仍不可用，node_modules 可能被占用损坏。
        echo  请先关闭前端预览窗口并重启本机 AI 助手，然后手动执行：
        echo    rmdir /s /q "%ROOT%video-frontend\node_modules"
        echo    cd /d "%ROOT%video-frontend" ^&^& npm install
        pause
        exit /b 1
    )
    cd /d "%ROOT%"
) else (
    echo [1/3] 前端依赖已安装
)

echo [2/3] 启动 API 后端...
REM 若存在 .venv 虚拟环境，则先激活再启动后端（避免依赖缺失）
if exist "%ROOT%.venv\Scripts\activate.bat" (
    echo      使用虚拟环境 .venv ...
    start "API后端" cmd /c "cd /d "%ROOT%" && call .venv\Scripts\activate.bat && python main.py > backend.log 2>&1"
) else (
    echo      未发现 .venv，使用系统 Python ...
    start "API后端" cmd /c "cd /d "%ROOT%" && python main.py > backend.log 2>&1"
)

REM 等待后端启动
echo [等待] 后端启动中...
ping -n 3 127.0.0.1 >nul

echo [3/3] 启动前端开发服务器...
start "前端" cmd /c "cd /d "%ROOT%video-frontend" && npm run dev"

echo.
echo ============================================
echo  启动完成!
echo.
echo  前端: http://localhost:5173
echo  后端: http://localhost:8000
echo  API文档: http://localhost:8000/docs
echo ============================================
echo.
echo  按任意键查看运行状态...
pause >nul

tasklist | findstr python
tasklist | findstr node
echo.
pause
