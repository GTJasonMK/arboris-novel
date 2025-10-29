@echo off
chcp 65001 >nul
echo ========================================
echo   Arboris Novel 开发环境启动脚本
echo ========================================
echo.

echo [1/3] 检查虚拟环境...
if not exist "backend\.venv\Scripts\activate.bat" (
    echo [错误] 后端虚拟环境不存在，请先运行：
    echo   cd backend
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo [2/3] 启动后端服务...
start "Arboris Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [3/3] 启动前端服务...
start "Arboris Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   启动完成！
echo   后端: http://localhost:8000
echo   前端: http://localhost:5173
echo   API文档: http://localhost:8000/docs
echo ========================================
echo.
echo 提示：关闭此窗口不会停止服务，请手动关闭后端和前端窗口
pause
