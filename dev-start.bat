@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   Arboris Novel 开发环境启动脚本
echo ========================================
echo.

echo [1/6] 检查虚拟环境...
if not exist "backend\.venv\Scripts\activate.bat" (
    echo [错误] 后端虚拟环境不存在，请先运行：
    echo   cd backend
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)
echo [完成] 虚拟环境检查通过
echo.

echo [2/6] 停止旧的后端进程...
set "found_process=0"

REM 查找所有占用8000端口的进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    set "pid=%%a"
    if not "!pid!"=="" (
        echo   停止进程 PID: !pid!
        taskkill /F /PID !pid! >nul 2>&1
        set "found_process=1"
    )
)

if "!found_process!"=="1" (
    echo [完成] 已停止旧的后端进程
    timeout /t 2 /nobreak >nul
) else (
    echo [跳过] 没有发现占用8000端口的进程
)
echo.

echo [3/6] 验证端口已释放...
set "port_check=0"
for /f %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" ^| find /c /v ""') do set "port_check=%%a"

if !port_check! GTR 0 (
    echo [警告] 8000端口仍被占用，尝试强制清理...
    taskkill /F /IM python.exe >nul 2>&1
    timeout /t 2 /nobreak >nul

    REM 再次检查
    set "port_recheck=0"
    for /f %%a in ('netstat -ano ^| findstr ":8000.*LISTENING" ^| find /c /v ""') do set "port_recheck=%%a"

    if !port_recheck! GTR 0 (
        echo [错误] 无法释放8000端口，请手动检查并停止相关进程
        echo 提示：运行命令查看占用进程： netstat -ano ^| findstr ":8000"
        pause
        exit /b 1
    )
)
echo [完成] 8000端口已释放
echo.

echo [4/6] 清理Python缓存...
set "cache_cleaned=0"

REM 删除所有 __pycache__ 目录
for /d /r "backend\app" %%d in (__pycache__) do (
    if exist "%%d" (
        rd /s /q "%%d" >nul 2>&1
        set "cache_cleaned=1"
    )
)

REM 删除所有 .pyc 文件
for /r "backend\app" %%f in (*.pyc) do (
    if exist "%%f" (
        del /f /q "%%f" >nul 2>&1
        set "cache_cleaned=1"
    )
)

if "!cache_cleaned!"=="1" (
    echo [完成] Python缓存已清理
) else (
    echo [跳过] 没有发现需要清理的缓存
)
echo.

echo [5/6] 启动后端服务...
start "Arboris Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && echo 正在启动后端服务... && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul
echo [完成] 后端服务已启动
echo.

echo [6/6] 启动前端服务...
start "Arboris Frontend" cmd /k "cd /d %~dp0frontend && echo 正在启动前端服务... && npm run dev"

echo [完成] 前端服务已启动
echo.

echo ========================================
echo   启动完成！
echo ========================================
echo.
echo   后端地址: http://localhost:8000
echo   前端地址: http://localhost:5173
echo   API文档:  http://localhost:8000/docs
echo.
echo ========================================
echo   重要提示
echo ========================================
echo.
echo 1. 后端和前端在独立窗口中运行
echo 2. 关闭此窗口不会停止服务
echo 3. 如需停止服务，请关闭对应的窗口
echo 4. 如遇到启动问题，请检查端口是否被占用
echo.
pause
