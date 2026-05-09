import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from pydantic import BaseModel
import pysrt
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 锁定物理路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRT_PATH = os.path.join(BASE_DIR, "data/final_american_beef_vlog.zh.srt")
VIDEO_PATH = os.path.join(BASE_DIR, "data/final_american_beef_vlog.mp4")
INDEX_PATH = os.path.join(BASE_DIR, "frontend/index.html")

class SubtitleItem(BaseModel):
    start: str
    end: str
    source: str
    english: str = ""
    index: int = None

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        return f.read()

@app.get("/api/subtitles")
async def get_subtitles():
    # 强制直接从 SRT 读取 (作为唯一真值)
    if not os.path.exists(SRT_PATH): return []
    try:
        subs = pysrt.open(SRT_PATH, encoding='utf-8')
        result = []
        for i, s in enumerate(subs):
            lines = s.text.split("\n")
            zh = lines[0] if len(lines) > 0 else ""
            en = lines[1] if len(lines) > 1 else ""
            result.append({
                "index": i+1,
                "start": str(s.start).replace('.', ','),
                "end": str(s.end).replace('.', ','),
                "source": zh,
                "english": en
            })
        return result
    except Exception as e:
        print(f"SRT Load Error: {e}")
        return []

@app.post("/api/save")
async def save_subtitles(data: List[SubtitleItem]):
    print(f"Direct saving to {SRT_PATH}...")
    try:
        new_srt = pysrt.SubRipFile()
        for i, item in enumerate(data):
            start = pysrt.SubRipTime.from_string(item.start.replace(',', '.'))
            end = pysrt.SubRipTime.from_string(item.end.replace(',', '.'))
            # 将中英双语作为文本直接存入 SRT
            text = f"{item.source}\n{item.english}" if item.english else item.source
            new_srt.append(pysrt.SubRipItem(index=i+1, start=start, end=end, text=text))
        new_srt.save(SRT_PATH, encoding='utf-8')
        return {"status": "success"}
    except Exception as e:
        print(f"Save Error: {e}")
        return Response(content=str(e), status_code=500)

@app.get("/video.mp4")
async def video_endpoint(range: str = None):
    if not os.path.exists(VIDEO_PATH): return Response(status_code=404)
    file_size = os.path.getsize(VIDEO_PATH)
    start, end = 0, file_size - 1
    if range:
        range_parts = range.replace("bytes=", "").split("-")
        start = int(range_parts[0])
        if len(range_parts) > 1 and range_parts[1]:
            end = int(range_parts[1])
    chunk_size = (end - start) + 1
    def get_chunk():
        with open(VIDEO_PATH, "rb") as f:
            f.seek(start)
            yield f.read(chunk_size)
    return StreamingResponse(
        get_chunk(), status_code=206,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": "video/mp4",
        }
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)
