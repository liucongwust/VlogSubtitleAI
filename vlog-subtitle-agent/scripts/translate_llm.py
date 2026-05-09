import pysrt
import sys
import os
import json
from openai import OpenAI

# 假设已经配置好了 OPENAI_API_KEY 环境变量
client = OpenAI()

def translate_text_batch(texts):
    prompt = f"""You are a professional subtitle translator. Translate the following Chinese vlog subtitles into idiomatic, natural English.
Keep the translation concise and suitable for video subtitles.
Return the result as a JSON array of strings, where each string is the translation of the corresponding input line.

Input:
{json.dumps(texts, ensure_ascii=False)}

Output:
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
        # 兼容不同的 JSON 返回格式
        if isinstance(data, dict):
            # 寻找可能的数组字段
            for val in data.values():
                if isinstance(val, list):
                    return val
        return data
    except Exception as e:
        print(f"Error parsing translation: {e}")
        return texts

def main(srt_path):
    if not os.path.exists(srt_path):
        print(f"File not found: {srt_path}")
        return

    subs = pysrt.open(srt_path, encoding='utf-8')
    all_texts = [sub.text.split('\n')[0].strip() for sub in subs]
    
    batch_size = 20
    translated_texts = []
    
    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i:i+batch_size]
        print(f"Translating batch {i//batch_size + 1}/{(len(all_texts)-1)//batch_size + 1}...")
        translated_batch = translate_text_batch(batch)
        # 确保翻译数量一致
        if len(translated_batch) != len(batch):
            print(f"Warning: batch size mismatch. Expected {len(batch)}, got {len(translated_batch)}")
            # 补齐或截断
            if len(translated_batch) < len(batch):
                translated_batch.extend(batch[len(translated_batch):])
            else:
                translated_batch = translated_batch[:len(batch)]
        
        translated_texts.extend(translated_batch)

    for i, sub in enumerate(subs):
        zh_text = all_texts[i]
        en_text = translated_texts[i]
        sub.text = f"{zh_text}\n{en_text}"

    output_path = srt_path.replace(".zh.srt", ".dual.srt")
    subs.save(output_path, encoding='utf-8')
    print(f"Bilingual subtitles saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python translate_llm.py <srt_path>")
    else:
        main(sys.argv[1])
