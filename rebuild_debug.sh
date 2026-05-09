#!/bin/bash
# 自动修复并重新打包调试版

echo "🛠️ 正在修复并生成调试版..."

# 修改打包命令：去掉 --noconsole，增加 --collect-all 以确保依赖完整
pyinstaller --name "VlogSubtitleEditor_Debug" \
            --windowed \
            --add-data "vlog-subtitle-agent/scripts/subtitle_editor/index.html:vlog-subtitle-agent/scripts/subtitle_editor" \
            --collect-all fastapi \
            --collect-all uvicorn \
            --collect-all webview \
            --clean \
            --noconfirm \
            macos_app.py

echo "✅ 调试版已生成。请运行以下命令查看详细日志："
echo "./dist/VlogSubtitleEditor_Debug.app/Contents/MacOS/VlogSubtitleEditor_Debug"
