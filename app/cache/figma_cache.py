# app/cache/figma_cache.py
"""
Система кэширования Figma структур и шаблонов
"""
import json
import logging
from pathlib import Path
from PIL import Image
from io import BytesIO
from typing import Tuple, Dict
import requests

from app.config import CFG

logger = logging.getLogger(__name__)

# Директория для кэша
CACHE_DIR = Path(CFG.BASE_DIR) / "figma_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"📁 Кэш директория: {CACHE_DIR}")


class FigmaCache:
    """Менеджер кэша Figma"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.structure_path = CACHE_DIR / f"{service_name}_structure.json"
        self.template_path = CACHE_DIR / f"{service_name}_template.png"
    
    def exists(self) -> bool:
        """Проверка наличия кэша"""
        return self.structure_path.exists() and self.template_path.exists()
    
    def save(self, structure: dict, template_bytes: bytes):
        """
        Сохранить структуру и шаблон в кэш
        
        Args:
            structure: JSON структура из Figma API
            template_bytes: PNG байты шаблона
        """
        try:
            # Сохраняем структуру
            self.structure_path.write_text(
                json.dumps(structure, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            # Сохраняем PNG
            self.template_path.write_bytes(template_bytes)
            
            logger.info(f"✅ Кэш сохранен для {self.service_name}")
            logger.info(f"   - Structure: {self.structure_path}")
            logger.info(f"   - Template: {self.template_path} ({len(template_bytes)} bytes)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша для {self.service_name}: {e}")
            raise
    
    def load(self) -> Tuple[dict, Image.Image]:
        """
        Загрузить структуру и шаблон из кэша
        
        Returns:
            (structure, template_image)
        
        Raises:
            FileNotFoundError: если кэш не найден
        """
        if not self.exists():
            raise FileNotFoundError(
                f"Кэш для {self.service_name} не найден. "
                f"Используйте команду /refresh_cache для создания кэша."
            )
        
        try:
            # Загружаем структуру
            structure = json.loads(
                self.structure_path.read_text(encoding='utf-8')
            )
            
            # Загружаем PNG
            template = Image.open(self.template_path).convert("RGBA")
            
            logger.info(f"📦 Кэш загружен для {self.service_name}")
            
            return structure, template
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша для {self.service_name}: {e}")
            raise
    
    def clear(self):
        """Удалить кэш"""
        try:
            if self.structure_path.exists():
                self.structure_path.unlink()
            if self.template_path.exists():
                self.template_path.unlink()
            
            logger.info(f"🗑️  Кэш удален для {self.service_name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления кэша для {self.service_name}: {e}")
            raise
    
    def get_info(self) -> dict:
        """Получить информацию о кэше"""
        if not self.exists():
            return {
                'exists': False,
                'service': self.service_name
            }
        
        structure_size = self.structure_path.stat().st_size
        template_size = self.template_path.stat().st_size
        structure_mtime = self.structure_path.stat().st_mtime
        
        return {
            'exists': True,
            'service': self.service_name,
            'structure_size': structure_size,
            'template_size': template_size,
            'total_size': structure_size + template_size,
            'modified_time': structure_mtime
        }


def get_all_cached_services() -> list:
    """Получить список всех сервисов с кэшем"""
    services = []
    
    for structure_file in CACHE_DIR.glob("*_structure.json"):
        service_name = structure_file.stem.replace("_structure", "")
        cache = FigmaCache(service_name)
        
        if cache.exists():
            services.append({
                'name': service_name,
                'info': cache.get_info()
            })
    
    return services


def clear_all_cache():
    """Удалить весь кэш"""
    count = 0
    
    for structure_file in CACHE_DIR.glob("*_structure.json"):
        service_name = structure_file.stem.replace("_structure", "")
        cache = FigmaCache(service_name)
        
        try:
            cache.clear()
            count += 1
        except Exception as e:
            logger.error(f"Ошибка удаления кэша {service_name}: {e}")
    
    logger.info(f"🗑️  Удалено кэшей: {count}")
    return count


# Удобные функции для быстрого доступа
def load_cache(service_name: str) -> Tuple[dict, Image.Image]:
    """Загрузить кэш для сервиса"""
    cache = FigmaCache(service_name)
    return cache.load()


def save_cache(service_name: str, structure: dict, template_bytes: bytes):
    """Сохранить кэш для сервиса"""
    cache = FigmaCache(service_name)
    cache.save(structure, template_bytes)


def cache_exists(service_name: str) -> bool:
    """Проверить наличие кэша"""
    cache = FigmaCache(service_name)
    return cache.exists()
