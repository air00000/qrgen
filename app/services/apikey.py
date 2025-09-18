import os
import json
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE = os.path.join(BASE_DIR, "..", "data", "api_keys.json")
KEYS_FILE = os.path.abspath(KEYS_FILE)  # ← на всякий случай

def _load_keys():
    print(os.path.exists(KEYS_FILE))
    if not os.path.exists(KEYS_FILE):
        return {}
    with open(KEYS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_keys(keys):
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)

def generate_key(name: str) -> str:
    keys = _load_keys()
    new_key = uuid.uuid4().hex
    keys[new_key] = name
    _save_keys(keys)
    return new_key

def get_all_keys() -> dict:
    return _load_keys()

def delete_key(key: str) -> bool:
    keys = _load_keys()
    if key in keys:
        del keys[key]
        _save_keys(keys)
        return True
