@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================
echo   Arboris Novel 快速初始化脚本
echo ============================================
echo.

REM 检查是否已存在 .env 文件
if exist "deploy\.env" (
    echo [警告] 检测到已存在 deploy\.env 文件
    choice /C YN /M "是否覆盖现有配置"
    if errorlevel 2 (
        echo 已取消初始化
        pause
        exit /b 0
    )
)

REM 复制 .env.example 为 .env
echo [1/4] 创建配置文件...
copy /Y "deploy\.env.example" "deploy\.env" >nul
if errorlevel 1 (
    echo [错误] 无法创建配置文件
    pause
    exit /b 1
)
echo       已创建 deploy\.env

REM 生成随机 SECRET_KEY（使用 PowerShell）
echo.
echo [2/4] 生成安全密钥...
for /f "delims=" %%i in ('powershell -Command "[guid]::NewGuid().ToString() + [guid]::NewGuid().ToString() -replace '-',''"') do set SECRET_KEY=%%i
echo       SECRET_KEY 已生成

REM 提示用户输入 OPENAI_API_KEY
echo.
echo [3/4] 配置 LLM API
echo       请输入您的 OpenAI API Key（或兼容的服务商 API Key）
echo       如果暂时没有，可以按回车跳过，稍后手动编辑 deploy\.env
echo.
set /p OPENAI_API_KEY="API Key: "

REM 提示用户输入管理员密码
echo.
echo [4/4] 设置管理员密码
echo       默认管理员账号: admin
echo       请设置一个安全的密码（至少 8 位，建议包含大小写字母和数字）
echo       如果使用默认密码 ChangeMe123! 请按回车
echo.
set /p ADMIN_PASSWORD="管理员密码: "
if "!ADMIN_PASSWORD!"=="" set ADMIN_PASSWORD=ChangeMe123!

REM 更新 .env 文件
echo.
echo [配置中] 写入配置文件...

REM 使用 PowerShell 进行配置文件替换（更可靠）
powershell -Command "(Get-Content 'deploy\.env') -replace '^SECRET_KEY=.*', 'SECRET_KEY=!SECRET_KEY!' | Set-Content 'deploy\.env'"
if not "!OPENAI_API_KEY!"=="" (
    powershell -Command "(Get-Content 'deploy\.env') -replace '^OPENAI_API_KEY=.*', 'OPENAI_API_KEY=!OPENAI_API_KEY!' | Set-Content 'deploy\.env'"
)
powershell -Command "(Get-Content 'deploy\.env') -replace '^ADMIN_DEFAULT_PASSWORD=.*', 'ADMIN_DEFAULT_PASSWORD=!ADMIN_PASSWORD!' | Set-Content 'deploy\.env'"

echo.
echo ============================================
echo   配置完成！
echo ============================================
echo.
echo 下一步操作：
echo.
if "!OPENAI_API_KEY!"=="" (
    echo   [重要] 请编辑 deploy\.env 文件，填写 OPENAI_API_KEY
    echo.
)
echo   方式一：使用 Docker 启动（推荐）
echo     cd deploy
echo     docker compose up -d
echo.
echo   方式二：本地开发模式
echo     后端: .\dev-start.bat 或 .\dev-restart.bat
echo     前端: cd frontend ^&^& npm install ^&^& npm run dev
echo.
echo   启动后访问: http://localhost（Docker）或 http://localhost:5173（本地）
echo   管理员账号: admin
echo   管理员密码: !ADMIN_PASSWORD!
echo.
echo ============================================
pause
