import os
import json
import uuid
from typing import Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE = os.path.join(BASE_DIR, "..", "data", "api_keys.json")
os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)

def _load_keys() -> Dict[str, str]:
    """Загружает API ключи из файла"""
    if not os.path.exists(KEYS_FILE):
        return {}
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_keys(keys: Dict[str, str]):
    """Сохраняет API ключи в файл"""
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)

def generate_key(name: str) -> str:
    """Генерирует новый API ключ"""
    keys = _load_keys()
    new_key = f"api_{uuid.uuid4().hex}"
    keys[new_key] = name
    _save_keys(keys)
    return new_key

def get_all_keys() -> Dict[str, str]:
    """Возвращает все API ключи"""
    return _load_keys()

def delete_key(key: str) -> bool:
    """Удаляет API ключ"""
    keys = _load_keys()
    if key in keys:
        del keys[key]
        _save_keys(keys)
        return True
    return False

def update_key_name(key: str, new_name: str) -> bool:
    """Обновляет название ключа"""
    keys = _load_keys()
    if key in keys:
        keys[key] = new_name
        _save_keys(keys)
        return True
    return False

def validate_key(api_key: str) -> bool:
    """Проверяет валидность API ключа"""
    keys = _load_keys()
    return api_key in keys

def get_key_name(api_key: str) -> Optional[str]:
    """Возвращает название ключа"""
    keys = _load_keys()
    return keys.get(api_key)