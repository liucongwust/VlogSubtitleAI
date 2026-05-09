import asyncio
from bilibili_api import video, sync
import requests
import os
import re
import sys

async def download_bili_video(bvid, output_dir="data"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    v = video.Video(bvid=bvid)
    info = await v.get_info()
    title = info['title']
    title = re.sub(r'[\\/:*?"<>|]', '_', title) # Clean filename
    
    print(f"Fetching download URL for: {title}")
    download_url = await v.get_download_url(0)
    
    # Get video and audio URLs (Bilibili often uses DASH)
    video_url = download_url['dash']['video'][0]['base_url']
    audio_url = download_url['dash']['audio'][0]['base_url']
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.bilibili.com'
    }
    
    video_path = f"{output_dir}/{title}_video.m4s"
    audio_path = f"{output_dir}/{title}_audio.m4s"
    final_path = f"{output_dir}/{title}.mp4"
    
    def download_file(url, path):
        print(f"Downloading {path}...")
        resp = requests.get(url, headers=headers, stream=True)
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
                    
    download_file(video_url, video_path)
    download_file(audio_url, audio_path)
    
    # Merge using ffmpeg
    print("Merging video and audio...")
    import subprocess
    subprocess.run(['ffmpeg', '-y', '-i', video_path, '-i', audio_path, '-c', 'copy', final_path], check=True)
    
    # Cleanup
    os.remove(video_path)
    os.remove(audio_path)
    
    return final_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download_bili.py <BVid> [output_dir]")
        sys.exit(1)
    
    bvid = sys.argv[1]
    output_dir = "data"
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
        
    if "BV" not in bvid:
        # Extract BV from URL
        match = re.search(r'(BV[a-zA-Z0-9]+)', bvid)
        if match:
            bvid = match.group(1)
            
    path = sync(download_bili_video(bvid, output_dir=output_dir))
    print(f"SUCCESS:{path}")
