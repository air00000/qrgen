# app/services/keystore.py
from __future__ import annotations
import json, os, secrets, string, time
from typing import List

DEFAULT_PATH = os.environ.get("KEYS_PATH", "data/api_keys.json")
os.makedirs(os.path.dirname(DEFAULT_PATH) or ".", exist_ok=True)

def _load(path: str = DEFAULT_PATH) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(k) for k in data]
    except Exception:
        pass
    return []

def _save(keys: List[str], path: str = DEFAULT_PATH):
    tmp = f"{path}.tmp.{int(time.time())}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def list_keys(path: str = DEFAULT_PATH) -> List[str]:
    return _load(path)

def add_key(key: str | None = None, path: str = DEFAULT_PATH) -> str:
    keys = _load(path)
    if key is None:
        alphabet = string.ascii_letters + string.digits
        key = "".join(secrets.choice(alphabet) for _ in range(40))
    if key not in keys:
        keys.append(key)
        _save(keys, path)
    return key

def remove_key(key: str, path: str = DEFAULT_PATH) -> bool:
    keys = _load(path)
    if key in keys:
        keys.remove(key)
        _save(keys, path)
        return True
    return False

def contains(key: str, path: str = DEFAULT_PATH) -> bool:
    return key in _load(path)
