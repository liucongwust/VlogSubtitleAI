#!/bin/bash

APP_NAME="VlogSubtitleEditor"
MAIN_SCRIPT="macos_app.py"
DATA_DIR="vlog-subtitle-agent/scripts/subtitle_editor"
TARGET_DIR="vlog-subtitle-agent/scripts/subtitle_editor"
BIN_DIR="vlog-subtitle-agent/bin"

echo "🚀 Starting STABLE build for $APP_NAME..."

# 清理
rm -rf build dist "$APP_NAME.spec"

# 打包
# 使用 collect-all 会引入太多冗余。我们改用 collect-submodules + collect-binaries
pyinstaller --name "$APP_NAME" \
            --windowed \
            --noconsole \
            --add-data "$DATA_DIR:$TARGET_DIR" \
            --add-data "$BIN_DIR:vlog-subtitle-agent/bin" \
            --collect-submodules torch \
            --collect-submodules whisper \
            --collect-submodules faster_whisper \
            --hidden-import "fastapi" \
            --hidden-import "uvicorn" \
            --hidden-import "webview" \
            --hidden-import "pysrt" \
            --hidden-import "openai" \
            --hidden-import "yt_dlp" \
            --hidden-import "bilibili_api" \
            --clean \
            --noconfirm \
            "$MAIN_SCRIPT"

if [ -d "dist/$APP_NAME.app" ]; then
    echo "✅ Build Successful!"
    
    # 生成 DMG
    echo "💿 Creating DMG image..."
    DMG_NAME="${APP_NAME}.dmg"
    rm -f "dist/$DMG_NAME"
    
    # 创建一个简单的 DMG，包含应用和到 /Applications 的快捷方式
    mkdir -p dist/dmg_root
    cp -R "dist/$APP_NAME.app" dist/dmg_root/
    ln -s /Applications dist/dmg_root/Applications
    
    hdiutil create -format UDZO -srcfolder dist/dmg_root -volname "$APP_NAME" "dist/$DMG_NAME"
    rm -rf dist/dmg_root
    
    if [ -f "dist/$DMG_NAME" ]; then
        echo "🎉 DMG created: $(pwd)/dist/$DMG_NAME"
        echo "💡 Double-click the DMG and drag the icon to Applications to INSTALL."
    else
        echo "❌ DMG creation failed."
        exit 1
    fi
else
    echo "❌ Build Failed."
    exit 1
fi
