@echo off
chcp 65001 >nul
title Antigravity Web Config Server
color 0a

echo ========================================================
echo        Antigravity 飞书集成与配置中心服务
echo ========================================================
echo.
echo 正在启动服务 (端口 9999)...

start "Flask Server" cmd /k "python server.py"

echo.
echo 等待服务初始化...
timeout /t 3 >nul

echo 正在打开浏览器...
start http://127.0.0.1:9999

echo ========================================================
echo 服务启动完成。如果要停止服务，请关闭此窗口及新弹出的终端窗口。
echo ========================================================
pause
