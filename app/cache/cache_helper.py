# app/cache/cache_helper.py
"""
Helper функции для использования кэша в генерации
"""
import logging
from PIL import Image

from app.cache.figma_cache import FigmaCache
from app.services.figma import get_template_json, export_frame_as_png, find_node
from app.config import CFG

logger = logging.getLogger(__name__)


class CacheLoadError(Exception):
    """Ошибка загрузки из кэша"""
    pass


def load_from_cache_or_figma(service_name: str, page: str, frame_name: str, use_cache: bool = True):
    """
    Загрузить шаблон из кэша или Figma
    
    Args:
        service_name: Имя сервиса для кэша (например, "marktplaats")
        page: Страница в Figma (например, "Page 2")
        frame_name: Имя фрейма (например, "marktplaats2_nl")
        use_cache: Использовать кэш если доступен (по умолчанию True)
        
    Returns:
        tuple: (template_json, template_img)
        
    Raises:
        CacheLoadError: если не удалось загрузить ни из кэша, ни из Figma
    """
    
    # Попытка загрузить из кэша
    if use_cache:
        cache = FigmaCache(service_name)
        
        if cache.exists():
            try:
                logger.info(f"📦 Загрузка {service_name} из кэша...")
                template_json, template_img = cache.load()
                logger.info(f"✅ {service_name} загружен из кэша")
                return template_json, template_img
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки из кэша {service_name}: {e}")
                logger.info(f"🔄 Fallback на Figma API...")
    
    # Fallback: загрузка из Figma API
    try:
        logger.info(f"📥 Загрузка {service_name} из Figma API...")
        
        template_json = get_template_json(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY)
        
        frame_node = find_node(template_json, page, frame_name)
        if not frame_node:
            raise CacheLoadError(f"Фрейм {frame_name} не найден на странице {page}")
        
        frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])
        
        from io import BytesIO
        template_img = Image.open(BytesIO(frame_png)).convert("RGBA")
        
        logger.info(f"✅ {service_name} загружен из Figma API")
        
        return template_json, template_img
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки {service_name} из Figma: {e}")
        raise CacheLoadError(
            f"Не удалось загрузить шаблон {service_name}. "
            f"Попробуйте обновить кэш командой /cache_all"
        ) from e


def should_use_cache() -> bool:
    """
    Определить нужно ли использовать кэш
    
    Returns:
        bool: True если кэш включен
    """
    # Можно добавить настройку в конфиг для отключения кэша
    return getattr(CFG, 'USE_CACHE', True)
