@echo off
chcp 65001 >nul
title ROB RUN 实时屏幕翻译工具
echo ============================================================
echo ROB RUN 实时屏幕翻译工具（免费版）v3 离线版
echo 原理：截屏 - OCR 认字 - 机器翻译 - 悬浮窗显示
echo 不改游戏文件、不注入、不读内存，不会被封号
echo 在线/离线可切换：F10 切换引擎，在线失败自动回落离线
echo ============================================================
echo.

echo [1/5] 正在检查 Python...
python --version >nul 2>&1
if errorlevel 1 (
echo.
echo [错误] 没有找到 Python！
echo.
echo 请先安装 Python，步骤：
echo 1. 打开 https://www.python.org/downloads/
echo 2. 下载 Python 3.11 或更新版本并安装
echo 3. 安装时务必勾选 "Add Python to PATH"（很重要！）
echo 4. 装好后重新双击 start.bat
echo.
pause
exit /b 1
)
python --version
echo Python 检查通过。
echo.

echo [2/5] 正在安装基础依赖（第一次运行需要几分钟，请耐心等待）...
pip install -r requirements.txt
if errorlevel 1 (
echo.
echo [提示] 默认源安装失败，正在尝试国内镜像...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
if errorlevel 1 (
echo.
echo [错误] 基础依赖安装失败，请检查网络后重新双击 start.bat。
echo 也可以手动运行：pip install -r requirements.txt
echo.
pause
exit /b 1
)
echo 基础依赖安装完成。
echo.

echo [3/5] 正在安装离线引擎依赖（轻量版：ctranslate2 + sentencepiece）...
echo 这是离线翻译真正用的引擎，装好就能断网翻，不需要 torch。
pip install -r requirements-offline.txt
if errorlevel 1 (
echo.
echo [提示] 默认源安装失败，正在尝试国内镜像...
pip install -r requirements-offline.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
)
if errorlevel 1 (
echo.
echo [提示] 离线引擎依赖这次没装上（在线模式不受影响）。
echo 想用离线模式时再手动运行：pip install -r requirements-offline.txt
echo.
)
echo.

echo [4/5] 正在尝试安装 Argos 官方库（可选，失败不影响使用）...
echo 官方库会额外下载 500MB+ 的 torch，网不好时很可能失败；
echo 失败也没关系：上面装好的轻量版照样能离线翻，效果一样。
pip install -r requirements-offline-full.txt
if errorlevel 1 (
echo.
echo [提示] Argos 官方库这次没装上——没关系，轻量离线路径已就绪。
echo 以后想补装再手动运行：pip install -r requirements-offline-full.txt
echo.
)
echo.

echo [5/5] 正在启动翻译工具...
echo 提示：请先把游戏设成"无边框窗口"模式再进游戏。
echo 提示：进游戏后按 F9 开关翻译，按 F10 切换在线/离线引擎。
echo 提示：首次用离线模式会联网下载一次模型（约 70MB），之后断网可用。
echo 提示：关掉这个黑窗口或按 Ctrl+C 退出。
echo.
python -u robrun_translator.py
echo.
echo 翻译工具已退出。
pause
