@echo off
chcp 65001 >nul
echo ========================================
echo   Arboris Novel 开发环境重启脚本
echo ========================================
echo.

echo [1/5] 停止现有后端进程...
taskkill /FI "WindowTitle eq Arboris Backend*" /T /F 2>nul
if %errorlevel% == 0 (
    echo   后端进程已停止
) else (
    echo   未发现运行中的后端进程
)

echo.
echo [2/5] 停止现有前端进程...
taskkill /FI "WindowTitle eq Arboris Frontend*" /T /F 2>nul
if %errorlevel% == 0 (
    echo   前端进程已停止
) else (
    echo   未发现运行中的前端进程
)

timeout /t 2 /nobreak >nul

echo.
echo [3/5] 检查虚拟环境...
if not exist "backend\.venv\Scripts\activate.bat" (
    echo [错误] 后端虚拟环境不存在
    pause
    exit /b 1
)

echo.
echo [4/5] 启动后端服务...
start "Arboris Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo.
echo [5/5] 启动前端服务...
start "Arboris Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   重启完成！
echo   后端: http://localhost:8000
echo   前端: http://localhost:5173
echo   API文档: http://localhost:8000/docs
echo ========================================
echo.
pause
