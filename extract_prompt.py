import json

path = r"C:\Users\MAHADEV YABAJI\.gemini\antigravity-ide\brain\1816522d-a93f-42d0-ba2b-10aa2c8ad83b\.system_generated\logs\transcript_full.jsonl"
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        if data.get("type") == "USER_INPUT":
            content = data.get("content", "")
            if "Ishita" in content:
                with open("challenge_brief.txt", "w", encoding="utf-8") as out:
                    out.write(content)
                print("Extracted challenge brief successfully!")
                break
