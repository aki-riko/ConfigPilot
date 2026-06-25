#!/usr/bin/env bash
# Codex 配置助手 —— macOS 打包脚本
# 策略:Nuitka 只出 standalone 目录(不用 --macos-create-app-bundle,绕开其内置 codesign --deep 在 CI 上的 FATAL),
#       脚本手动组装 .app bundle + 自己 ad-hoc 签名(不带 --deep,整体签,报错可见) + hdiutil 打 DMG。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
APP_NAME="CodexConfig"
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
  <key>CFBundleIdentifier</key><string>life.9li.codexconfig</string>
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

# 3) ad-hoc 签名(不用 --deep;先签内部 dylib/so,再签整个 bundle)
echo "[INFO] 开始 ad-hoc 签名..."
# 先逐个签嵌套的 .dylib/.so(避免 bundle 签名时内部未签报错)
while IFS= read -r -d '' f; do
  codesign --force --sign - --timestamp=none "$f"
done < <(find "$APP_BUNDLE/Contents/MacOS" \( -name "*.dylib" -o -name "*.so" \) -type f -print0)
# 不单独签 Contents/MacOS/ 下的主可执行文件(codesign 会因 Info.plist 的 CFBundleExecutable
# 指向它而报 "bundle format unrecognized"——主程序由签整个 bundle 时自动处理)
# 直接签整个 .app bundle
codesign --force --sign - --timestamp=none "$APP_BUNDLE"
echo "[INFO] 验证签名:"
codesign --verify --verbose=2 "$APP_BUNDLE" || { echo "[ERROR] 签名验证失败"; exit 1; }
echo "[OK] ad-hoc 签名完成"

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

