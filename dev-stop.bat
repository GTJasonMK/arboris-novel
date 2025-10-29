@echo off
chcp 65001 >nul
echo ========================================
echo   停止开发环境
echo ========================================
echo.

echo [1/2] 停止后端进程...
taskkill /FI "WindowTitle eq Arboris Backend*" /T /F 2>nul
if %errorlevel% == 0 (
    echo   后端进程已停止
) else (
    echo   未发现运行中的后端进程
)

echo.
echo [2/2] 停止前端进程...
taskkill /FI "WindowTitle eq Arboris Frontend*" /T /F 2>nul
if %errorlevel% == 0 (
    echo   前端进程已停止
) else (
    echo   未发现运行中的前端进程
)

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
echo.
pause
