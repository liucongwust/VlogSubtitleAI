import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from huggingface_hub import snapshot_download
print("Starting download...")
try:
    path = snapshot_download("Systran/faster-whisper-tiny", cache_dir="./test_model")
    print("Downloaded to:", path)
except Exception as e:
    print("Error:", e)
