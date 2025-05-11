import json
import os

HISTORY_FILE = "chat_histories.json"
MEMORY_FILE = "chat_memories.json"

def load_json(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}

    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print(f"[Warning] Failed to parse {path}, using empty fallback.")
            return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_all():
    return load_json(HISTORY_FILE), load_json(MEMORY_FILE)

def save_all(histories, memories):
    save_json(HISTORY_FILE, histories)
    save_json(MEMORY_FILE, memories)
