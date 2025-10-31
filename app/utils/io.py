import os
from app.config import CFG

def ensure_dirs():
    os.makedirs(CFG.PHOTO_DIR, exist_ok=True)
    os.makedirs(CFG.TEMP_DIR, exist_ok=True)

def cleanup_paths(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
