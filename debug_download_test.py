import os
import sys
from yt_dlp import YoutubeDL

url = "https://www.bilibili.com/video/BV1kUXsB3EsZ"
output_dir = "data/debug_test"
os.makedirs(output_dir, exist_ok=True)

# 模仿 backend_main.py 中的逻辑
def find_ffmpeg():
    search_paths = [
        os.path.expanduser("~/work/softwares/miniforge3/bin/ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/usr/bin/ffmpeg"
    ]
    for p in search_paths:
        if os.path.exists(p): return p
    return "ffmpeg"

ffmpeg_exe = find_ffmpeg()
print(f"FFmpeg found at: {ffmpeg_exe}")

ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
    'ffmpeg_location': ffmpeg_exe,
    'nocheckcertificate': True,
    'http_headers': {'Referer': 'https://www.bilibili.com/'}
}

# 检查是否有 cookie 文件
cookie_file = os.path.join(os.path.expanduser("~"), "VlogStudioData", "bili_cookies.txt")
if os.path.exists(cookie_file):
    print(f"Using cookie file: {cookie_file}")
    ydl_opts['cookiefile'] = cookie_file
else:
    print("No cookie file found at the expected location.")

try:
    with YoutubeDL(ydl_opts) as ydl:
        print("Extracting info...")
        info = ydl.extract_info(url, download=True)
        print(f"✅ Success! Title: {info.get('title')}")
except Exception as e:
    print(f"❌ Failed! Error: {str(e)}")
