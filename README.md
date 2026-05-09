# VlogSubtitleAI 🎬

**VlogSubtitleAI** 是一款专为视频博主（Vloggers）设计的全自动化 AI 字幕处理工具。它集成了视频下载、语音识别（ASR）、LLM 智能翻译以及字幕压制功能，旨在大幅提升 Vlog 的后期制作效率。

---

## ✨ 功能特性

- 📥 **智能下载**：支持 Bilibili 等主流视频平台的链接下载（集成 Bilibili 扫码登录）。
- 🎙️ **高精度识别**：基于 `Faster-Whisper` 技术，支持从 `tiny` 到 `large-v3` 的多种模型，快速生成带时间轴的中文/英文原始字幕。
- 🤖 **LLM 智能翻译**：支持通过 DeepSeek / OpenAI 等大模型进行上下文感知的精准翻译，拒绝机械翻译感。
- ✍️ **双语编辑器**：内置 Web 端字幕编辑器，支持实时预览、快速修改和中英双语对照。
- 🛠️ **一键压制**：基于 FFmpeg 的硬件加速压制，支持一键将字幕烧录（Hardcode）进视频。
- 📦 **开箱即用**：提供 macOS 原生 DMG 安装包，支持拖拽安装，界面简洁直观。

---

## 🚀 快速开始 (开发者模式)

如果您希望从源码运行或进行二次开发，请参考以下步骤：

### 1. 克隆仓库
```bash
git clone git@github.com:liucongwust/VlogSubtitleAI.git
cd VlogSubtitleAI
```

### 2. 环境准备
项目依赖 Python 3.9+。建议使用 Miniforge 或虚拟环境：

```bash
# 安装核心依赖
pip install -r requirements.txt  # (请确保已生成该文件，或手动安装下述包)
pip install fastapi uvicorn pywebview pyinstaller torch faster-whisper pysrt yt-dlp openai qrcode pillow
```

### 3. 系统依赖
确保您的系统中已安装 `FFmpeg`：
```bash
brew install ffmpeg
```

### 4. 运行应用
```bash
python macos_app.py
```

---

## 📦 打包与分发 (macOS)

项目内置了一键打包脚本，可以直接生成可直接分发的 `.dmg` 文件：

```bash
# 赋予脚本执行权限
chmod +x build_macos.sh

# 开始打包 (生成 dist/VlogSubtitleAI.dmg)
./build_macos.sh
```

---

## 🛠️ 技术栈

- **前端**: HTML5 / JavaScript (Tailwind CSS 风格)
- **后端**: Python / FastAPI
- **GUI 框架**: PyWebView (原生 macOS 容器)
- **AI 引擎**: Faster-Whisper, OpenAI API
- **视频处理**: FFmpeg, yt-dlp

---

## 📂 目录结构说明

- `macos_app.py`: 应用入口，负责管理后端进程和 WebView 窗口。
- `vlog-subtitle-agent/scripts/subtitle_editor/`: 核心业务代码（后端逻辑与前端界面）。
- `build_macos.sh`: macOS 自动化打包脚本。
- `data/`: 存储应用配置、下载的视频及临时生成的字幕（已加入 .gitignore）。
- `models/`: 存放识别模型（首次运行会自动下载）。

---

## 📜 许可证

本项目遵循 MIT 开源协议。

---

*由 Gemini CLI 自动生成。*
