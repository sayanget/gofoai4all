@echo off
chcp 65001 >nul
title Antigravity Workflow Core - 飞书诊断引擎
echo ========================================================
echo        启动 Antigravity 飞书 AI 诊断配置与服务引擎       
echo ========================================================
echo.
echo [1/2] 正在启动本地 Flask 服务器 (端口 9999)...

:: 使用 start 命令新开一个窗口运行 python 服务，避免阻塞脚本
start "Antigravity Flask Server" cmd /c "python server.py"

echo [2/2] 等待服务启动并自动打开浏览器...
:: 等待 3 秒钟确保服务器启动
timeout /t 3 >nul

:: 启动默认浏览器打开配置中心
start http://127.0.0.1:9999

echo.
echo 启动完成！
echo 如果浏览器没有自动打开，请手动访问: http://127.0.0.1:9999
echo （服务器后台窗口已在单独的 cmd 窗口中运行，请勿关闭）
echo.
pause
