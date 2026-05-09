import os
import subprocess
import whisper
from yt_dlp import YoutubeDL
import sys

def download_video(url, output_dir="data"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'{output_dir}/%(title)s.%(ext)s',
        'quiet': False,
        'no_warnings': True,
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

def generate_subtitles(video_path, output_srt):
    print(f"Generating English subtitles for {video_path}...")
    model = whisper.load_model("base") # base is faster, small/medium is more accurate
    
    # task='translate' will translate any language to English
    result = model.transcribe(video_path, task="translate", verbose=False)
    
    with open(output_srt, "w", encoding="utf-8") as f:
        for i, segment in enumerate(result['segments']):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            f.write(f"{i + 1}\n{start} --> {end}\n{text}\n\n")
    return output_srt

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def add_subtitles_to_video(video_path, srt_path, output_path):
    print(f"Adding subtitles to video: {output_path}")
    # Hardcode subtitles into video (burn-in)
    # We need to escape the path for ffmpeg filters
    srt_path_escaped = srt_path.replace(":", "\\:").replace("'", "'\\''")
    command = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', f"subtitles='{srt_path_escaped}'",
        '-c:a', 'copy',
        output_path
    ]
    subprocess.run(command, check=True)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_bilibili.py <url>")
        sys.exit(1)
    
    video_path = "data/今天在广东佛山的肉厂买牛肉吃到爽，看看要花多少？.mp4"
    try:
        # Step 2: Generate SRT
        print("Step 1: Generating English subtitles via Whisper (Translate mode)...")
        base_name = os.path.splitext(video_path)[0]
        srt_file = base_name + ".en.srt"
        generate_subtitles(video_path, srt_file)
        print(f"Subtitles saved to: {srt_file}")
        
        # Step 3: Merge
        print("Step 2: Merging subtitles into video (Burn-in)...")
        final_video = base_name + "_with_en_subs.mp4"
        add_subtitles_to_video(video_path, srt_file, final_video)
        print(f"Final video processed: {final_video}")
        
    except Exception as e:
        print(f"Error: {e}")
