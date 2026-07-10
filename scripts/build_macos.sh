#!/usr/bin/env bash
# ConfigPilot —— macOS 打包脚本
# 策略:Nuitka 只出 standalone 目录(不用 --macos-create-app-bundle,绕开其内置 codesign --deep 在 CI 上的 FATAL),
#       脚本手动组装 .app bundle + 自己 ad-hoc 签名(不带 --deep,整体签,报错可见) + hdiutil 打 DMG。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
APP_NAME="ConfigPilot"
APP_VER="${APP_VER:-1.0.0}"
ARCH="$(uname -m)"   # arm64 或 x86_64

# 动态定位 site-packages 里的 prismqml 包目录(各机路径不同,禁止硬编码)
FQ="$("$PY" -c 'import os, prismqml; print(os.path.dirname(prismqml.__file__))')"
echo "[INFO] prismqml 路径: $FQ"

rm -rf build
mkdir -p build

# 1) Nuitka standalone(普通目录,不创建 app bundle → 不触发 Nuitka 内置签名)
"$PY" -m nuitka \
  --standalone \
  --assume-yes-for-downloads \
  --enable-plugin=pyside6 \
  --include-qt-plugins=qml \
  --include-data-dir=qml=qml \
  --include-data-dir=resources=resources \
  --include-data-dir="$FQ=prismqml" \
  --include-data-files=providers.json=providers.json \
  --include-data-files=model_profiles.json=model_profiles.json \
  --include-package=prismqml \
  --include-package=backend \
  --output-dir=build \
  --output-filename="$APP_NAME" \
  main.py

DIST_DIR="build/main.dist"
if [ ! -d "$DIST_DIR" ]; then
  echo "[ERROR] 未找到 standalone 产物 $DIST_DIR,build 内容:"; ls -la build; exit 1
fi
echo "[OK] standalone 目录: $DIST_DIR"

#__APP_ASSEMBLY__
# 2) 手动组装 .app bundle
APP_BUNDLE="build/${APP_NAME}.app"
rm -rf "$APP_BUNDLE"
MACOS_DIR="$APP_BUNDLE/Contents/MacOS"
RES_DIR="$APP_BUNDLE/Contents/Resources"
mkdir -p "$MACOS_DIR" "$RES_DIR"

# standalone 全部内容(可执行 + 依赖)放进 Contents/MacOS
# BSD cp: 源带尾斜杠 = 复制目录内容(含隐藏文件)进目标,不嵌套
cp -R "$DIST_DIR"/ "$MACOS_DIR"/
chmod +x "$MACOS_DIR/$APP_NAME"

# 图标
if [ -f "resources/app_icon.icns" ]; then
  cp "resources/app_icon.icns" "$RES_DIR/app_icon.icns"
  ICON_PLIST="<key>CFBundleIconFile</key><string>app_icon</string>"
else
  echo "[WARN] 缺 resources/app_icon.icns"; ICON_PLIST=""
fi

# Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key><string>${APP_NAME}</string>
  <key>CFBundleExecutable</key><string>${APP_NAME}</string>
  <key>CFBundleIdentifier</key><string>life.9li.configpilot</string>
  <key>CFBundleVersion</key><string>${APP_VER}</string>
  <key>CFBundleShortVersionString</key><string>${APP_VER}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  ${ICON_PLIST}
</dict>
</plist>
PLIST
echo "[OK] app bundle 组装完成: $APP_BUNDLE"

# 3) 不做代码签名。
# 原因:ad-hoc 签名(codesign -s -)对 Nuitka 平铺布局的 .app 会报 "bundle format
# unrecognized",且 ad-hoc 签名本来也不能让 .app 免 macOS Gatekeeper——
# 客户首次打开仍需"右键→打开"。所以不签名,交付未签名 .app,客户右键打开即可。
echo "[INFO] 跳过代码签名(交付未签名 .app,客户首次需右键→打开绕过 Gatekeeper)"

# 4) 打 DMG
mkdir -p dist
DMG_PATH="dist/${APP_NAME}_${APP_VER}_${ARCH}.dmg"
rm -f "$DMG_PATH"
STAGING="build/dmg_staging"
rm -rf "$STAGING"; mkdir -p "$STAGING"
cp -R "$APP_BUNDLE" "$STAGING/${APP_NAME}.app"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG_PATH"
echo "[OK] DMG 产物: $DMG_PATH"
