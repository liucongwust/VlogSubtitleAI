import pysrt
import os
import shutil

print("1. Editing SRT timeline...")
srt_path = "data/final_american_beef_vlog.zh.srt"
backup_srt = "data/final_american_beef_vlog_backup.zh.srt"

if not os.path.exists(backup_srt):
    shutil.copy2(srt_path, backup_srt)

subs = pysrt.open(srt_path, encoding='utf-8')

kept_subs = pysrt.SubRipFile()
for sub in subs:
    # 丢弃前 10 秒的字幕
    if sub.start.ordinal >= 10000:
        kept_subs.append(sub)

# 把剩下的字幕整体向前移动 5 秒（因为我们去掉了 10 秒，又在前面加了 5 秒，差值为 -5）
kept_subs.shift(seconds=-5)

# 创建新的片头字幕 (0~5秒)
intro_sub = pysrt.SubRipItem(
    index=1,
    start=pysrt.SubRipTime(0, 0, 0, 0),
    end=pysrt.SubRipTime(0, 0, 4, 900),
    text="看广东人对吃有多讲究。\nSee how particular Guangdong people are about eating."
)

final_subs = pysrt.SubRipFile()
final_subs.append(intro_sub)

# 合并并重新编号
for i, sub in enumerate(kept_subs):
    sub.index = i + 2
    final_subs.append(sub)

final_subs.save("data/edited_vlog.srt", encoding='utf-8')

print("2. Cutting and concatenating video...")
orig_vid = "data/final_american_beef_vlog.mp4"
backup_vid = "data/final_american_beef_vlog_backup.mp4"
new_raw_vid = "data/edited_vlog.mp4"

if not os.path.exists(backup_vid):
    shutil.copy2(orig_vid, backup_vid)

# FFmpeg 剪辑逻辑：
# v0, a0: 截取 184s 到 189s (3:04~3:09)
# v1, a1: 截取 10s 到 结尾
# 拼合 v0 + v1
cmd_edit = f"""ffmpeg -i {orig_vid} -filter_complex "[0:v]trim=start=184:end=189,setpts=PTS-STARTPTS[v0]; [0:a]atrim=start=184:end=189,asetpts=PTS-STARTPTS[a0]; [0:v]trim=start=10,setpts=PTS-STARTPTS[v1]; [0:a]atrim=start=10,asetpts=PTS-STARTPTS[a1]; [v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" -c:v libx264 -c:a aac -y {new_raw_vid}"""

os.system(cmd_edit)

print("3. Swapping files for frontend and backend...")
# 覆盖原文件，这样后端不用改代码，网页直接生效
os.rename(new_raw_vid, orig_vid)
os.rename("data/edited_vlog.srt", srt_path)

print("4. Burning subtitles into final video...")
final_output = "data/final_vlog_edited_with_subtitles.mp4"
cmd_burn = f"""ffmpeg -i {orig_vid} -vf "subtitles={srt_path}:force_style='FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1,Alignment=2'" -c:a copy -y {final_output}"""
os.system(cmd_burn)

print("All done! Final video is ready.")
