import os

def cleanup_paths(paths):
    """Очистка временных файлов если они существуют"""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except:
                pass