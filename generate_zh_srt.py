import os
import sys
from faster_whisper import WhisperModel

def format_timestamp(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def generate_chinese_subtitles(video_path, output_srt):
    print(f"Generating original Chinese subtitles for {video_path} using faster-whisper...")
    
    # 使用本地下载好的 large-v3 模型获取最佳中文识别效果
    # 指向你刚刚通过 git lfs 下载好的文件夹
    model_size = "./faster-whisper-large-v3"
    print(f"Loading local model from {model_size}...")
    model = WhisperModel(model_size, device="auto", compute_type="default")
    
    # beam_size=5 可以在识别速度和精度之间取得很好的平衡
    # condition_on_previous_text=False 可以很大程度减少中文幻觉和重复
    segments, info = model.transcribe(video_path, beam_size=5, language="zh", condition_on_previous_text=False)
    
    print("Detected language '%s' with probability %f" % (info.language, info.language_probability))
    
    with open(output_srt, "w", encoding="utf-8") as f:
        # faster-whisper 的 segments 是一个生成器，遍历时才会逐步推理和生成
        for i, segment in enumerate(segments):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            text = segment.text.strip()
            if text:
                output_line = f"[{start} --> {end}] {text}"
                print(output_line)  # 实时打印到终端查看
                f.write(f"{i + 1}\n{start} --> {end}\n{text}\n\n")
                f.flush() # 确保实时写入磁盘
    return output_srt

if __name__ == "__main__":
    video_path = "data/final_american_beef_vlog.mp4"
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        sys.exit(1)
        
    base_name = os.path.splitext(video_path)[0]
    zh_srt_file = base_name + ".zh.srt"
    generate_chinese_subtitles(video_path, zh_srt_file)
    print(f"Chinese subtitles generated: {zh_srt_file}")
