@echo off
chcp 65001 >nul
title Antigravity Workflow Core - 一键启动面板
color 0b

:menu
cls
echo ========================================================
echo        Antigravity 飞书 AI 诊断引擎 - 一键启动面板       
echo ========================================================
echo.
echo   [1] 启动 Web 配置与服务中心 (自动打开浏览器)
echo   [2] 运行 AI 每日考核诊断流水线 (执行 main.py)
echo   [3] 运行完整测试流水线 (执行 run_pipeline.py 测试)
echo   [0] 退出
echo.
echo ========================================================
set /p choice="请选择要执行的操作编号 [0-3]: "

if "%choice%"=="1" goto start_server
if "%choice%"=="2" goto run_main
if "%choice%"=="3" goto run_test
if "%choice%"=="0" exit

echo.
echo 输入无效，请重新输入...
timeout /t 2 >nul
goto menu

:start_server
echo.
echo 正在清理旧的 server.py 进程...
wmic process where "CommandLine like '%%server.py%%' and Name='python.exe'" call terminate >nul 2>&1
echo 正在启动服务 (端口 9999)...
start "Antigravity Flask Server" cmd /k "python server.py"
echo 等待服务启动并自动打开浏览器...
timeout /t 3 >nul
start http://127.0.0.1:9999
echo 启动完成！如果浏览器没有自动打开，请手动访问: http://127.0.0.1:9999
pause
goto menu

:run_main
echo.
echo 正在运行每日 AI 诊断与飞书推送流水线 (main.py)...
echo ========================================================
python main.py
echo ========================================================
echo 诊断与推送执行完毕！
pause
goto menu

:run_test
echo.
echo 正在运行本地流水线测试 (run_pipeline.py)...
echo ========================================================
python run_pipeline.py
echo ========================================================
echo 测试执行完毕，结果已输出至当前目录的文件中。
pause
goto menu
