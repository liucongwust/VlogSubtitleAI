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
        self.selected_model = "base" # 默认平衡
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

# --- Finder 交互 ---
@app.post("/api/open-model-folder")
async def open_model_folder():
    if os.path.exists(state.model_dir):
        subprocess.run(["open", state.model_dir]); return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/open-folder")
async def open_folder():
    if state.srt_path and os.path.exists(state.srt_path): subprocess.run(["open", "-R", state.srt_path]); return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/open-video-folder")
async def open_video_folder():
    if state.video_path and os.path.exists(state.video_path): subprocess.run(["open", "-R", state.video_path]); return {"status": "ok"}
    return {"status": "error"}

# --- ASR 逻辑 (支持模型切换) ---
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
                load_root = state.model_dir
            elif os.path.exists(direct_path_model) and os.path.exists(os.path.join(direct_path_model, "config.json")):
                model_to_load = direct_path_model
                load_root = state.model_dir
            else:
                model_to_load = state.selected_model
                load_root = state.model_dir
            
            print(f"DEBUG: Initializing Faster-Whisper '{model_to_load}' in {load_root}")
            state.asr_progress = 0
            state.asr_status_msg = f"正在初始化 {state.selected_model} 模型 (若本地无缓存将自动高速下载)..."
            model = WhisperModel(model_to_load, device="cpu", compute_type="int8", download_root=load_root)
            
            state.asr_status_msg = "模型载入完成，正在分析音频结构..."
            segments, info = model.transcribe(state.video_path, beam_size=5)
            new_srt = pysrt.SubRipFile()
            state.asr_status_msg = "正在识别并生成字幕..."
            for i, s in enumerate(segments): 
                new_srt.append(pysrt.SubRipItem(index=i+1, start=pysrt.SubRipTime(seconds=s.start), end=pysrt.SubRipTime(seconds=s.end), text=s.text.strip()))
                if info.duration > 0:
                    state.asr_progress = min(100, int((s.end / info.duration) * 100))
            new_srt.save(state.srt_path, encoding='utf-8'); state.current_step = "edit_zh"
        except Exception as e: 
            import traceback
            traceback.print_exc()
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
        state.last_error = ""
        try:
            # Check for direct path first in root or in model_dir
            direct_path_root = os.path.join(ROOT_DIR, f"faster-whisper-{state.selected_model}")
            direct_path_model = os.path.join(state.model_dir, f"faster-whisper-{state.selected_model}")
            
            if os.path.exists(direct_path_root) and os.path.exists(os.path.join(direct_path_root, "config.json")):
                model_to_load = direct_path_root
                load_root = state.model_dir
            elif os.path.exists(direct_path_model) and os.path.exists(os.path.join(direct_path_model, "config.json")):
                model_to_load = direct_path_model
                load_root = state.model_dir
            else:
                model_to_load = state.selected_model
                load_root = state.model_dir
                
            state.asr_progress = 0
            state.asr_status_msg = f"正在专门下载 {state.selected_model} 模型到本地..."
            download_model(model_to_load, cache_dir=load_root)
            state.current_step = "idle"
            state.asr_status_msg = ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            state.last_error = f"模型下载失败: {str(e)}"
            state.current_step = "idle"
        finally:
            state.is_running = False
    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}

@app.post("/api/select-model-dir-dialog")
def select_model_dir_dialog():
    try:
        script = 'tell application "SystemUIServer"\nactivate\nset thePath to POSIX path of (choose folder with prompt "选择自定义模型存放目录 (将全局生效)")\nend tell\nreturn thePath'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            state.model_dir = result.stdout.strip()
            return {"status": "ok", "path": state.model_dir}
        else:
            print("Dialog failed or canceled:", result.stderr)
    except Exception as e:
        print(f"Error opening dialog: {e}")
    return {"status": "cancelled"}

# --- 保持配置管理 / 视频流 / 下载 / 翻译逻辑 ---
@app.get("/api/status")
async def get_status():
    model_name = state.selected_model
    direct_path_root = os.path.join(ROOT_DIR, f"faster-whisper-{model_name}")
    direct_path_model = os.path.join(state.model_dir, f"faster-whisper-{model_name}")
    hf_cache_dir = os.path.join(state.model_dir, f"models--Systran--faster-whisper-{model_name}")
    
    if os.path.exists(direct_path_root) and os.path.exists(os.path.join(direct_path_root, "config.json")):
        has_model = True
    elif os.path.exists(direct_path_model) and os.path.exists(os.path.join(direct_path_model, "config.json")):
        has_model = True
    else:
        has_model = os.path.exists(hf_cache_dir) or os.path.exists(os.path.join(state.model_dir, model_name))
    return {
        "video_path": state.video_path, "srt_path": state.srt_path, "current_step": state.current_step,
        "download_status": state.download_status, "download_progress": state.download_progress,
        "translate_progress": state.translate_progress, "source_type": state.source_type,
        "logged_in": os.path.exists(AUTH_FILE), "last_error": state.last_error, 
        "model_downloaded": has_model, "selected_model": state.selected_model,
        "api_key": state.api_key, "llm_model": state.llm_model, "model_dir": state.model_dir,
        "is_running": getattr(state, "is_running", False), "asr_progress": getattr(state, "asr_progress", 0), 
        "asr_status_msg": getattr(state, "asr_status_msg", ""), "burn_progress": getattr(state, "burn_progress", 0)
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
    start = max(0, min(start, fs - 1)); end = max(start, min(end, fs - 1))
    def stream():
        with open(state.video_path, "rb") as f:
            f.seek(start); remaining = (end - start) + 1
            while remaining > 0:
                data = f.read(min(1024*512, remaining))
                if not data: break
                yield data; remaining -= len(data)
    return StreamingResponse(stream(), status_code=206, headers={"Accept-Ranges":"bytes", "Content-Range":f"bytes {start}-{end}/{fs}", "Content-Length":str((end-start)+1), "Content-Type":"video/mp4", "Cache-Control":"no-cache"})

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
    state.api_key = req.get("api_key", ""); state.llm_model = req.get("llm_model", "deepseek-chat"); state.base_url = req.get("base_url", "https://api.deepseek.com")
    try:
        with open(CONFIG_FILE, "w") as f: json.dump({"api_key": state.api_key, "llm_model": state.llm_model, "base_url": state.base_url}, f)
        return {"status": "ok"}
    except Exception as e: return JSONResponse(status_code=500, content={"message": str(e)})

@app.post("/api/set-step")
async def set_step(req: dict): state.current_step = req.get("step", "idle"); return {"status": "ok"}
@app.post("/api/load-local")
async def load_local(req: dict):
    p = req.get("video_path")
    if not os.path.exists(p): return JSONResponse(status_code=404, content={})
    state.video_path = p; state.source_type = "local"; state.srt_path = os.path.splitext(p)[0] + ".srt"
    state.current_step = "edit_zh" if os.path.exists(state.srt_path) else "asr"
    return {"status": "success"}

@app.get("/api/subtitles")
async def get_subtitles():
    if not state.srt_path or not os.path.exists(state.srt_path): return JSONResponse(content=[])
    subs = pysrt.open(state.srt_path, encoding='utf-8')
    return [{"index": i+1, "start": str(s.start).replace('.', ','), "end": str(s.end).replace('.', ','), "source": s.text.split("\n")[0], "english": s.text.split("\n")[1] if "\n" in s.text else ""} for i, s in enumerate(subs)]

def run_translation(lang: str):
    if not state.api_key: state.last_error = "Key missing"; state.current_step = "edit_zh"; return
    state.current_step = "translating"; state.translate_progress = 0
    state.is_running = True
    try:
        with state.file_lock:
            subs = pysrt.open(state.srt_path, encoding='utf-8')
            client = OpenAI(api_key=state.api_key, base_url=state.base_url); total = len(subs)
            for i in range(0, total, 15):
                batch = subs[i:i+15]; texts = [s.text.split('\n')[0].strip() for s in batch]
                res = client.chat.completions.create(model=state.llm_model, messages=[{"role": "user", "content": f"Translate to {lang}. JSON output: {json.dumps(texts, ensure_ascii=False)}"}], response_format={"type": "json_object"} if "deepseek" in state.llm_model.lower() or "gpt" in state.llm_model.lower() or "qwen" in state.llm_model.lower() or "glm" in state.llm_model.lower() else None)
                raw_content = res.choices[0].message.content.strip()
                if raw_content.startswith('```json'): raw_content = raw_content[7:-3]
                raw = json.loads(raw_content); lst = raw if isinstance(raw, list) else list(raw.values())[0]
                for j, s in enumerate(batch): 
                    en_text = lst[j] if isinstance(lst, list) and j < len(lst) else ""
                    s.text = f"{s.text.splitlines()[0]}\n{en_text}"
                state.translate_progress = int((i + len(batch)) / total * 100)
            subs.save(state.srt_path, encoding='utf-8')
        state.current_step = "edit_en"
    except Exception as e: 
        import traceback
        traceback.print_exc()
        state.last_error = str(e); state.current_step = "edit_zh"
    finally:
        state.is_running = False

@app.post("/api/translate")
async def start_translate(req: dict):
    threading.Thread(target=run_translation, args=(req.get("target_lang"),), daemon=True).start()
    return {"status": "started"}

@app.post("/api/start-burn")
async def start_burn():
    def _run():
        state.is_running = True
        state.current_step = "burning"
        state.burn_progress = 0
        try:
            import re
            duration = 1.0
            res = subprocess.run([FFMPEG_EXE, "-i", state.video_path], capture_output=True, text=True)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
            if m: duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
            
            out = os.path.splitext(state.video_path)[0] + "_final.mp4"
            cmd = [FFMPEG_EXE, "-y", "-i", state.video_path, "-vf", f"subtitles='{state.srt_path}'", "-c:a", "copy", out]
            
            process = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
            for line in process.stderr:
                tm = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                if tm:
                    curr = int(tm.group(1)) * 3600 + int(tm.group(2)) * 60 + float(tm.group(3))
                    state.burn_progress = min(99, int((curr / duration) * 100))
            
            process.wait()
            if process.returncode != 0:
                raise Exception("压制视频失败，请查看日志。")
                
            state.burn_progress = 100
            state.video_path = out; state.current_step = "done"
        except Exception as e: 
            import traceback
            traceback.print_exc()
            state.last_error = str(e); state.current_step = "edit_en"
        finally:
            state.is_running = False
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.post("/api/download")
async def start_download(req: dict):
    url = req.get("url")
    def _run():
        try:
            state.source_type = "url"; state.download_status = "downloading"; state.current_step = "downloading"
            output_dir = os.path.join(DATA_DIR, "downloads"); os.makedirs(output_dir, exist_ok=True)
            ydl_opts = {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 'outtmpl': f'{output_dir}/%(title)s.%(ext)s', 'progress_hooks': [download_hook], 'ffmpeg_location': FFMPEG_EXE, 'nocheckcertificate': True, 'http_headers': {'Referer': 'https://www.bilibili.com/'}}
            if os.path.exists(COOKIE_FILE): ydl_opts['cookiefile'] = COOKIE_FILE
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True); state.video_path = ydl.prepare_filename(info)
                state.srt_path = os.path.splitext(state.video_path)[0] + ".srt"
                state.download_status = "success"; state.current_step = "asr"
        except Exception as e: state.last_error = str(e); state.download_status = "error"; state.current_step = "idle"
    threading.Thread(target=_run, daemon=True).start(); return {"status": "started"}

@app.get("/api/bili/qrcode")
async def get_bili_qrcode():
    try:
        from bilibili_api import login_v2
        state.login_obj = login_v2.QrCodeLogin(); await state.login_obj.generate_qrcode()
        url = getattr(state.login_obj, "_QrCodeLogin__qr_link"); img = qrcode.make(url); buf = io.BytesIO(); img.save(buf, format='PNG')
        return {"qrcode": base64.b64encode(buf.getvalue()).decode('utf-8')}
    except Exception as e: return JSONResponse(status_code=500, content={"message": str(e)})

@app.get("/api/bili/check-login")
async def check_bili_login():
    if not state.login_obj: return {"status": "error"}
    try:
        from bilibili_api import login_v2
        status = await state.login_obj.check_state()
        if status == login_v2.QrCodeLoginEvents.DONE:
            cred = state.login_obj.get_credential()
            auth_data = {"sessdata": cred.sessdata, "bili_jct": cred.bili_jct, "buvid3": cred.buvid3, "dedeuserid": cred.dedeuserid}
            with open(AUTH_FILE, "w") as f: json.dump(auth_data, f)
            save_as_netscape_cookies(auth_data, COOKIE_FILE); return {"status": "success"}
        return {"status": "waiting" if status != login_v2.QrCodeLoginEvents.CONF else "scanned"}
    except: return {"status": "error"}

@app.get("/")
async def get_index():
    with open(INDEX_PATH, 'r', encoding='utf-8') as f: return HTMLResponse(content=f.read())

@app.get("/logo.png")
async def get_logo():
    logo_path = os.path.join(DATA_DIR, "logo.png")
    if os.path.exists(logo_path): return FileResponse(logo_path)
    return Response(status_code=404)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)
