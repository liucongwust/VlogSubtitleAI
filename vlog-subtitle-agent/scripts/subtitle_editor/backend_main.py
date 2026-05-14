import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import json
import pysrt
import uvicorn
import subprocess
import threading
import sys
import whisper
from faster_whisper import WhisperModel, download_model
import asyncio
import io
import base64
import qrcode
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from yt_dlp import YoutubeDL
from openai import OpenAI
from bilibili_api import login_v2, sync

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 路径自适应
if getattr(sys, 'frozen', False):
    CURRENT_DIR = os.path.join(sys._MEIPASS, "vlog-subtitle-agent", "scripts", "subtitle_editor")
    BIN_DIR = os.path.join(sys._MEIPASS, "vlog-subtitle-agent", "bin")
    DATA_DIR = os.path.join(os.path.expanduser("~"), "VlogStudioData")
    ROOT_DIR = DATA_DIR
else:
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    BIN_DIR = os.path.join(os.path.dirname(os.path.dirname(CURRENT_DIR)), "bin")
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
    DATA_DIR = os.path.join(ROOT_DIR, "data")

os.makedirs(DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def find_ffmpeg():
    search_paths = [os.path.join(BIN_DIR, "ffmpeg"), os.path.expanduser("~/work/softwares/miniforge3/bin/ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]
    for p in search_paths:
        if os.path.exists(p): return p
    return "ffmpeg"

FFMPEG_EXE = find_ffmpeg()
INDEX_PATH = os.path.join(CURRENT_DIR, "index.html")
AUTH_FILE = os.path.join(DATA_DIR, "bili_auth.json")
COOKIE_FILE = os.path.join(DATA_DIR, "bili_cookies.txt")

class AppState:
    def __init__(self):
        self.video_path = ""; self.srt_path = ""; self.download_progress = 0
        self.download_status = "idle"; self.last_error = ""; self.translate_progress = 0
        self.current_step = "idle"; self.source_type = "local"
        self.selected_model = "base" 
        self.model_dir = os.path.join(ROOT_DIR, "models")
        os.makedirs(self.model_dir, exist_ok=True)
        self.file_lock = threading.Lock(); self.login_obj = None
        self.api_key = ""; self.llm_model = "deepseek-chat"; self.base_url = "https://api.deepseek.com"
        self.is_running = False; self.asr_progress = 0; self.asr_status_msg = ""
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    conf = json.load(f); self.api_key = conf.get("api_key", ""); self.llm_model = conf.get("llm_model", "deepseek-chat"); self.base_url = conf.get("base_url", "https://api.deepseek.com")
            except: pass

state = AppState()

# --- 智能元数据生成 (支持多语言) ---
@app.post("/api/generate-metadata")
async def generate_metadata(req: dict):
    if not state.api_key:
        return JSONResponse(status_code=400, content={"message": "请先配置 API Key"})
    
    target_lang = req.get("lang", "English")
    state.is_running = True
    state.current_step = "metadata_gen"
    
    def _run():
        try:
            subs = pysrt.open(state.srt_path, encoding='utf-8')
            context_text = "\n".join([s.text.split('\n')[0] for s in subs[:50]])
            
            prompt = f"""
            Analyze the following video transcript and generate 3 catchy, high-engagement video titles.
            IMPORTANT: ALL outputs (titles, summary, and keywords) MUST be in {target_lang}.
            
            Content context:
            {context_text}
            
            Output strictly in JSON format:
            {{
              "titles": ["Catchy Title 1", "Catchy Title 2", "Catchy Title 3"],
              "summary": "An engaging video summary in {target_lang}.",
              "keywords": ["tag1", "tag2"]
            }}
            """
            
            client = OpenAI(api_key=state.api_key, base_url=state.base_url)
            res = client.chat.completions.create(
                model=state.llm_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            global metadataResult
            metadataResult = json.loads(res.choices[0].message.content.strip())
            state.current_step = "metadata_review"
        except Exception as e:
            state.last_error = str(e)
            state.current_step = "metadata"
        finally:
            state.is_running = False

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}

metadataResult = None

@app.get("/api/get-metadata-result")
async def get_metadata_result():
    return metadataResult or {}

@app.post("/api/set-title")
async def set_title(req: dict):
    selected_title = req.get("title", "")
    print(f"User selected title: {selected_title}")
    return {"status": "ok"}

# --- Finder 交互 ---
@app.post("/api/open-model-folder")
async def open_model_folder():
    if os.path.exists(state.model_dir):
        subprocess.run(["open", state.model_dir]); return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/open-folder")
async def open_folder():
    if state.srt_path and os.path.exists(state.srt_path): 
        subprocess.run(["open", "-R", state.srt_path]); return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/open-video-folder")
async def open_video_folder():
    if state.video_path and os.path.exists(state.video_path): 
        subprocess.run(["open", "-R", state.video_path]); return {"status": "ok"}
    return {"status": "error"}

# --- ASR 逻辑 ---
@app.post("/api/start-asr")
async def start_asr():
    def _run():
        state.is_running = True
        state.current_step = "asr"; state.last_error = ""
        try:
            direct_path_root = os.path.join(ROOT_DIR, f"faster-whisper-{state.selected_model}")
            direct_path_model = os.path.join(state.model_dir, f"faster-whisper-{state.selected_model}")
            if os.path.exists(direct_path_root) and os.path.exists(os.path.join(direct_path_root, "config.json")):
                model_to_load = direct_path_root
            elif os.path.exists(direct_path_model) and os.path.exists(os.path.join(direct_path_model, "config.json")):
                model_to_load = direct_path_model
            else:
                model_to_load = state.selected_model
            
            model = WhisperModel(model_to_load, device="cpu", compute_type="int8", download_root=state.model_dir)
            segments, info = model.transcribe(state.video_path, beam_size=5)
            new_srt = pysrt.SubRipFile()
            for i, s in enumerate(segments): 
                new_srt.append(pysrt.SubRipItem(index=i+1, start=pysrt.SubRipTime(seconds=s.start), end=pysrt.SubRipTime(seconds=s.end), text=s.text.strip()))
                if info.duration > 0: state.asr_progress = min(100, int((s.end / info.duration) * 100))
            new_srt.save(state.srt_path, encoding='utf-8'); state.current_step = "edit_zh"
        except Exception as e: 
            state.last_error = str(e); state.current_step = "asr"
        finally:
            state.is_running = False
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.post("/api/set-model")
async def set_model(req: dict):
    state.selected_model = req.get("model", "base"); return {"status": "ok"}

@app.post("/api/download-model-only")
async def download_model_only():
    def _run():
        state.is_running = True
        state.current_step = "asr"
        try:
            download_model(state.selected_model, cache_dir=state.model_dir)
            state.current_step = "idle"
        except Exception as e: state.last_error = str(e)
        finally: state.is_running = False
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.get("/api/status")
async def get_status():
    return {
        "video_path": state.video_path, "srt_path": state.srt_path, "current_step": state.current_step,
        "download_status": state.download_status, "download_progress": state.download_progress,
        "translate_progress": state.translate_progress, "source_type": state.source_type,
        "logged_in": os.path.exists(AUTH_FILE), "last_error": state.last_error, 
        "selected_model": state.selected_model, "api_key": state.api_key, "llm_model": state.llm_model, 
        "model_dir": state.model_dir, "is_running": state.is_running, "asr_progress": state.asr_progress
    }

@app.get("/video.mp4")
async def video_endpoint(request: Request):
    if not state.video_path or not os.path.exists(state.video_path): return Response(status_code=404)
    fs = os.path.getsize(state.video_path); rh = request.headers.get("Range")
    start, end = 0, fs - 1
    if rh:
        rs = rh.replace("bytes=", "").split("-")
        if rs[0]: start = int(rs[0])
        if len(rs) > 1 and rs[1]: end = int(rs[1])
    def stream():
        with open(state.video_path, "rb") as f:
            f.seek(start); remaining = (end - start) + 1
            while remaining > 0:
                data = f.read(min(1024*512, remaining))
                if not data: break
                yield data; remaining -= len(data)
    return StreamingResponse(stream(), status_code=206, headers={"Accept-Ranges":"bytes", "Content-Range":f"bytes {start}-{end}/{fs}", "Content-Length":str((end-start)+1), "Content-Type":"video/mp4"})

@app.post("/api/save")
async def save_subtitles(data: List[dict]):
    with state.file_lock:
        new_srt = pysrt.SubRipFile()
        for i, item in enumerate(data):
            text = f"{item['source']}\n{item['english']}" if item.get('english') else item['source']
            new_srt.append(pysrt.SubRipItem(index=i+1, start=pysrt.SubRipTime.from_string(item['start'].replace(',', '.')), end=pysrt.SubRipTime.from_string(item['end'].replace(',', '.')), text=text))
        new_srt.save(state.srt_path, encoding='utf-8')
    return {"status": "success"}

@app.post("/api/set-config")
async def set_config(req: dict):
    state.api_key = req.get("api_key", ""); state.llm_model = req.get("llm_model", "deepseek-chat")
    with open(CONFIG_FILE, "w") as f: json.dump({"api_key": state.api_key, "llm_model": state.llm_model}, f)
    return {"status": "ok"}

@app.get("/api/subtitles")
async def get_subtitles():
    if not state.srt_path or not os.path.exists(state.srt_path): return []
    subs = pysrt.open(state.srt_path, encoding='utf-8')
    return [{"index": i+1, "start": str(s.start).replace('.', ','), "end": str(s.end).replace('.', ','), "source": s.text.split("\n")[0], "english": s.text.split("\n")[1] if "\n" in s.text else ""} for i, s in enumerate(subs)]

@app.post("/api/translate")
async def start_translate(req: dict):
    target_lang = req.get("target_lang", "English")
    def _run():
        state.is_running = True; state.current_step = "translating"; state.translate_progress = 0
        try:
            subs = pysrt.open(state.srt_path, encoding='utf-8'); client = OpenAI(api_key=state.api_key, base_url=state.base_url); total = len(subs)
            for i in range(0, total, 15):
                batch = subs[i:i+15]; texts = [s.text.split('\n')[0].strip() for s in batch]
                res = client.chat.completions.create(model=state.llm_model, messages=[{"role": "user", "content": f"Translate to {target_lang}. JSON: {json.dumps(texts)}"}], response_format={"type": "json_object"})
                lst = list(json.loads(res.choices[0].message.content).values())[0]
                for j, s in enumerate(batch): s.text = f"{s.text.splitlines()[0]}\n{lst[j]}"
                state.translate_progress = int((i + len(batch)) / total * 100)
            subs.save(state.srt_path, encoding='utf-8'); state.current_step = "edit_en"
        except Exception as e: state.last_error = str(e); state.current_step = "edit_zh"
        finally: state.is_running = False
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.post("/api/start-burn")
async def start_burn():
    def _run():
        state.is_running = True; state.current_step = "burning"
        try:
            out = os.path.splitext(state.video_path)[0] + "_final.mp4"
            subprocess.run([FFMPEG_EXE, "-y", "-i", state.video_path, "-vf", f"subtitles='{state.srt_path}'", "-c:a", "copy", out], check=True)
            state.video_path = out; state.current_step = "done"
        except Exception as e: state.last_error = str(e); state.current_step = "edit_en"
        finally: state.is_running = False
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.post("/api/download")
async def start_download(req: dict):
    url = req.get("url")
    def _run():
        try:
            state.current_step = "downloading"; output_dir = os.path.join(DATA_DIR, "downloads"); os.makedirs(output_dir, exist_ok=True)
            ydl_opts = {'outtmpl': f'{output_dir}/%(title)s.%(ext)s'}
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True); state.video_path = ydl.prepare_filename(info)
                state.srt_path = os.path.splitext(state.video_path)[0] + ".srt"; state.current_step = "asr"
        except Exception as e: state.last_error = str(e); state.current_step = "idle"
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.post("/api/load-local")
async def load_local(req: dict):
    p = req.get("video_path")
    if os.path.exists(p):
        state.video_path = p; state.srt_path = os.path.splitext(p)[0] + ".srt"
        state.current_step = "edit_zh" if os.path.exists(state.srt_path) else "asr"
        return {"status": "success"}
    return JSONResponse(status_code=404, content={})

@app.post("/api/set-step")
async def set_step(req: dict): state.current_step = req.get("step", "idle"); return {"status": "ok"}
@app.get("/")
async def get_index(): return HTMLResponse(content=open(INDEX_PATH, 'r').read())
@app.get("/logo.png")
async def get_logo(): return FileResponse(os.path.join(DATA_DIR, "logo.png")) if os.path.exists(os.path.join(DATA_DIR, "logo.png")) else Response(status_code=404)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)
