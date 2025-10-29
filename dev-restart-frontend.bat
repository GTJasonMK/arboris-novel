@echo off
chcp 65001 >nul
echo ========================================
echo   重启前端服务
echo ========================================
echo.

echo [1/2] 停止现有前端进程...
taskkill /FI "WindowTitle eq Arboris Frontend*" /T /F 2>nul
if %errorlevel% == 0 (
    echo   前端进程已停止
) else (
    echo   未发现运行中的前端进程
)

timeout /t 2 /nobreak >nul

echo.
echo [2/2] 启动前端服务...
start "Arboris Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ========================================
echo   前端重启完成！
echo   地址: http://localhost:5173
echo ========================================
echo.
pause
