@echo off
chcp 65001 >nul
REM Codex 配置助手 —— Nuitka 打包(独立 venv: quicksketch\.venv, prismqml 0.2.15)
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe
set FQ=.venv\Lib\site-packages\prismqml

REM 换参数前先删 build 防 getWindowsShortPathName 崩(记忆经验)
if exist build rmdir /s /q build

"%PY%" -m nuitka ^
  --standalone ^
  --assume-yes-for-downloads ^
  --enable-plugin=pyside6 ^
  --include-qt-plugins=qml ^
  --include-data-dir=qml=qml ^
  --include-data-dir=resources=resources ^
  --include-data-dir="%FQ%=prismqml" ^
  --include-data-files=providers.json=providers.json ^
  --include-package=prismqml ^
  --include-package=backend ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=resources\app_icon.ico ^
  --output-dir=build ^
  --output-filename=CodexConfig.exe ^
  --company-name=9li ^
  --product-name=Codex配置助手 ^
  --file-version=1.0.1 ^
  main.py

echo.
echo ===== 打包结束,产物在 build\main.dist\ =====
