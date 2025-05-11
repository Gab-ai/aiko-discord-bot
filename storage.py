import json
import os

HISTORY_FILE = "chat_histories.json"
MEMORY_FILE = "chat_memories.json"

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_all():
    return load_json(HISTORY_FILE), load_json(MEMORY_FILE)

def save_all(histories, memories):
    save_json(HISTORY_FILE, histories)
    save_json(MEMORY_FILE, memories)
