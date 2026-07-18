@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
set "FQ=.venv\Lib\site-packages\prismqml"
set "APP_VER=1.0.13"

if not exist "%PY%" (
  echo [ERROR] Missing %PY%
  exit /b 1
)

if exist build rmdir /s /q build

call "%PY%" -m nuitka ^
  --standalone ^
  --assume-yes-for-downloads ^
  --enable-plugin=pyside6 ^
  --include-qt-plugins=qml ^
  --include-data-dir=qml=qml ^
  --include-data-dir=resources=resources ^
  --include-data-dir="%FQ%=prismqml" ^
  --include-data-files=providers.json=providers.json ^
  --include-data-files=model_profiles.json=model_profiles.json ^
  --include-data-files=app_config.json=app_config.json ^
  --include-package=prismqml ^
  --include-package=backend ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=resources\app_icon.ico ^
  --output-dir=build ^
  --output-filename=ConfigPilot.exe ^
  --company-name=9li ^
  --product-name=ConfigPilot ^
  --file-version=%APP_VER% ^
  main.py

if errorlevel 1 exit /b %errorlevel%

echo.
echo ===== Build complete: build\main.dist\ConfigPilot.exe =====
