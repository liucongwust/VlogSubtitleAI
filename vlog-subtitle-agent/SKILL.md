---
name: vlog-subtitle-agent
description: Professional end-to-end Vlog subtitle extraction, interactive bilingual translation, video cutting, and hard-subtitle burning. Use when you need to process video subtitles accurately, translate them idiomatically without overriding original language corrections, and edit/burn the final video.
---

# Vlog Subtitle Agent

## Overview

This skill provides a robust, professional pipeline for extracting, translating, and hard-coding bilingual subtitles into Vlogs. It relies on a local `faster-whisper` model for high-accuracy extraction and provides a FastAPI-powered interactive web editor for user corrections.

The translation step guarantees 100% preservation of the user's manual original-language corrections by only appending idiomatic English translations to the second line of the SRT chunks. Finally, it handles FFmpeg-based video cutting, intro creation, subtitle shifting, and burning.

## 1. Extracting Original Subtitles

To extract high-accuracy original subtitles (e.g., Chinese) from a raw `.mp4` video:
- Use `scripts/generate_zh_srt.py`.
- It loads `faster-whisper` (`large-v3` by default) to transcribe the video.
- **Why large-v3**: It prevents the "long silences" and "hallucination" issues common with smaller whisper models in complex audio environments.

## 2. Interactive Subtitle Editor

Instead of manually editing SRT files or overriding user data automatically via Python dictionaries, we serve a native web-based Subtitle Editor:
1.  **Backend**: `scripts/subtitle_editor/backend_main.py` is a FastAPI server that reads/writes directly to the `.srt` file. It parses each SRT chunk and extracts the first line (source) and second line (English translation).
2.  **Frontend**: `scripts/subtitle_editor/index.html` is an interactive UI served on port 8100. It features a side-by-side editing interface (Chinese above, English below) and auto-saves the edits seamlessly using debounced API calls.

*Important Note: Always use the direct-to-SRT reading logic. Do not rely on intermediate JSON files (`subtitles.json`) as they can easily get out of sync with the true SRT file during complex pipelines.*

## 3. Safe Bilingual Translation

The golden rule of translation: **NEVER OVERWRITE THE ORIGINAL LANGUAGE.**

When the user asks you to translate the subtitles:
1. Use `scripts/safe_translate.py` (which implements the LLM-based logic).
2. It parses the SRT and extracts the **first line** of text from each chunk (the user's corrected source text).
3. It generates an idiomatic English translation using an LLM mapping dictionary (or live API).
4. It safely appends the translation as the **second line** in the chunk: `f"{original_source}\\n{new_english}"`.
5. It saves the SRT back. This preserves user corrections perfectly while providing bilingual context.

## 4. Video Editing & Hard Subtitle Burning

Vlogs often require intro-manipulation or pacing adjustments. Use `scripts/burn_and_cut.py` as a reference for complex FFmpeg operations:
1. **Removing dead space**: E.g., `trim=start=10` removes the first 10 seconds.
2. **Creating Highlights**: Extracting a specific high-tension clip (e.g., 3:04~3:09) and moving it to the front as an intro sequence.
3. **Shifting Subtitles**: If 10 seconds are removed and 5 seconds are added, the overall timeline shrinks by 5 seconds. Use `pysrt` to shift all subtitles: `subs.shift(seconds=-5)`.
4. **Burning**: Use FFmpeg's `subtitles` filter with custom styling to burn the dual-language SRT onto the final video.
   - Example style: `force_style='FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=1,Alignment=2'`

## Rules and Pitfalls

*   **No Auto-Correct on Source Language**: If the user says "I have corrected the Chinese text", DO NOT run any script that attempts to "guess" or "auto-correct" their source text. Your job is ONLY to translate the English portion.
*   **SRT is the Source of Truth**: Intermediate files like JSON can cause data loss. The FastAPI backend must directly write `pysrt.SubRipFile` objects to the active `.srt` file.
*   **FFmpeg Filters**: Always use `-filter_complex` when concatenating multiple audio/video streams to prevent desynchronization.
