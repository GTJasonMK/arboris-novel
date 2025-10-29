@echo off
chcp 65001 >nul
echo ========================================
echo   重启后端服务
echo ========================================
echo.

echo [1/3] 停止现有后端进程...
taskkill /FI "WindowTitle eq Arboris Backend*" /T /F 2>nul
if %errorlevel% == 0 (
    echo   后端进程已停止
) else (
    echo   未发现运行中的后端进程
)

timeout /t 2 /nobreak >nul

echo.
echo [2/3] 检查虚拟环境...
if not exist "backend\.venv\Scripts\activate.bat" (
    echo [错误] 后端虚拟环境不存在
    pause
    exit /b 1
)

echo.
echo [3/3] 启动后端服务...
start "Arboris Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo.
echo ========================================
echo   后端重启完成！
echo   地址: http://localhost:8000
echo   API文档: http://localhost:8000/docs
echo ========================================
echo.
pause
