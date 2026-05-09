# Videos Project Context

## 项目概览
该项目位于 `/Users/liucong/work/videos`，目前处于初始阶段。根据项目名称和全局开发背景，该项目旨在处理、存储或展示视频资源，可能作为 **PianoVision AI** 的配套组件或独立的视频全栈应用。

### 核心技术栈 (建议)
- **Frontend:** React (TypeScript), Tailwind CSS, Vite
- **Backend:** Python (FastAPI), Pydantic, SQLAlchemy/Tortoise-ORM
- **Video Processing:** FFmpeg (用于转码、切片、提取元数据)
- **Storage:** 本地文件系统或 S3 兼容存储 (用于存储大规模视频文件)

## 目录结构 (预想)
```text
videos/
├── GEMINI.md          # 项目指令上下文 (当前文件)
├── frontend/          # React 前端代码
├── backend/           # FastAPI 后端代码
├── data/              # 原始视频和处理后的媒体文件
├── scripts/           # 视频处理脚本 (如 FFmpeg 自动化)
└── docker-compose.yml # 容器化配置
```

## 开发规范 (遵循全局原则)
1. **代码风格:** 遵循 Google Python Style Guide 和 React 最佳实践。
2. **API 契约:** 前后端交互必须定义严谨的 TypeScript 接口和 Pydantic 模型。
3. **视频处理:** 复杂的视频转码任务应异步执行（如使用 Celery 或 FastAPI 的 BackgroundTasks）。
4. **性能:** 针对大文件传输，后端应支持 Range Requests 以实现视频流式播放。

## 待办事项 (TODO)
- [ ] 初始化 Git 仓库。
- [ ] 构建后端 FastAPI 骨架，支持视频元数据管理。
- [ ] 构建前端 React 播放器界面。
- [ ] 配置 FFmpeg 处理工作流。

## 构建与运行
- **Backend:** `uvicorn app.main:app --reload` (预估)
- **Frontend:** `npm run dev` (预估)

---
*注意: 本文件由 Gemini CLI 在项目初始化阶段自动生成，请随着项目的推进实时更新。*
