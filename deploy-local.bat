@echo off
chcp 65001 >nul
echo ========================================
echo Arboris-Novel 一键部署启动
echo （本地开发模式 - 不使用 Docker）
echo ========================================
echo.

echo [1/4] 停止现有服务...
echo 停止后端...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)

echo 停止前端...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a 2>nul
)
timeout /t 2 /nobreak >nul
echo ✅ 已停止旧服务
echo.

echo [2/4] 检查并安装依赖...
cd backend
if not exist ".venv" (
    echo 创建 Python 虚拟环境...
    python -m venv .venv
)
echo 安装/更新 Python 依赖...
call .venv\Scripts\activate
pip install -r requirements.txt -q
if %ERRORLEVEL% NEQ 0 (
    echo 警告：部分依赖安装失败，尝试重新安装...
    pip install -r requirements.txt
)
cd ..

cd frontend
if not exist "node_modules" (
    echo 安装前端依赖...
    call npm install
) else (
    echo ✅ 前端依赖已就绪
)
cd ..
echo.

echo [3/4] 启动后端服务...
cd backend
start "Arboris Backend" cmd /k ".venv\Scripts\activate && python -m uvicorn app.main:app --reload --port 8000"
cd ..
timeout /t 3 /nobreak >nul
echo ✅ 后端已启动
echo.

echo [4/4] 启动前端服务...
cd frontend
start "Arboris Frontend" cmd /k "npm run dev"
cd ..
timeout /t 3 /nobreak >nul
echo ✅ 前端已启动
echo.

echo ========================================
echo 🎉 部署完成！服务已启动
echo ========================================
echo.
echo 📍 访问地址:
echo    前端: http://localhost:5173
echo    后端: http://127.0.0.1:8000
echo    API文档: http://127.0.0.1:8000/docs
echo.
echo ✨ 新功能已上线:
echo    【蓝图迭代优化】
echo    - 生成蓝图后，点击"优化蓝图"按钮
echo    - 输入优化指令（如"让主角更复杂"）
echo    - AI 会在现有蓝图基础上针对性改进
echo    - 可以多次优化直到满意
echo.
echo 💡 提示:
echo    - 两个命令窗口将保持打开（后端和前端）
echo    - 关闭窗口即可停止对应服务
echo    - 代码修改会自动重载（热更新）
echo.
pause
