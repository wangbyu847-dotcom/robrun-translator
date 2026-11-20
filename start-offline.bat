@echo off
chcp 65001 >nul
title ROB RUN 实时屏幕翻译工具（离线模式）
echo ============================================================
echo ROB RUN 实时屏幕翻译工具（免费版）v3 离线版
echo 离线模式启动：用 Argos 本地模型翻译，断网也能用
echo 首次运行会联网下载一次模型（约 70MB），之后断网可用
echo ============================================================
echo.

echo [1/3] 正在检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
echo.
echo [错误] 没有找到 Python！
echo.
echo 请先安装 Python，步骤：
echo 1. 打开 https://www.python.org/downloads/
echo 2. 下载 Python 3.11 或更新版本并安装
echo 3. 安装时务必勾选 "Add Python to PATH"（很重要！）
echo 4. 装好后重新双击 start-offline.bat
echo.
pause
exit /b 1
)
python --version
echo Python 检查通过。
echo.

echo [2/3] 正在安装基础依赖（第一次运行需要几分钟，请耐心等待）...
pip install -r requirements.txt
if errorlevel 1 (
echo.
echo [提示] 默认源安装失败，正在尝试国内镜像...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
if errorlevel 1 (
echo.
echo [错误] 基础依赖安装失败，请检查网络后重新双击 start-offline.bat。
echo 也可以手动运行：pip install -r requirements.txt
echo.
pause
exit /b 1
)
echo 基础依赖安装完成。
echo.

echo [3/3] 正在安装离线引擎依赖（轻量版：ctranslate2 + sentencepiece）...
pip install -r requirements-offline.txt
if errorlevel 1 (
echo.
echo [提示] 默认源安装失败，正在尝试国内镜像...
pip install -r requirements-offline.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
if errorlevel 1 (
echo.
echo [错误] 离线引擎依赖安装失败，离线模式跑不起来。
echo 请检查网络后重新双击 start-offline.bat，也可以手动运行：
echo pip install -r requirements-offline.txt
echo.
pause
exit /b 1
)
echo 离线引擎依赖安装完成。
echo.

echo 正在用离线模式启动（相当于 start.bat 加 --offline）...
echo 提示：请先把游戏设成"无边框窗口"模式再进游戏。
echo 提示：进游戏后按 F9 开关翻译，按 F10 可切回在线引擎。
echo 提示：首次用离线模式会联网下载一次模型（约 70MB），之后断网可用。
echo 提示：关掉这个黑窗口或按 Ctrl+C 退出。
echo.
python -u robrun_translator.py --offline
echo.
echo 翻译工具已退出。
pause
