# app/services/cache_wrapper.py
"""
Обёртки для функций генерации с автоматическим использованием кэша
"""
import logging
from PIL import Image
import io

from app.cache.figma_cache import FigmaCache
from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.config import CFG

logger = logging.getLogger(__name__)


def load_template_with_cache(service_name: str, page: str, frame_name: str):
    """
    Загрузить template_json и frame_img с использованием кэша если доступен
    
    Args:
        service_name: Имя сервиса для кэша (например "marktplaats", "subito")
        page: Название страницы в Figma (например "Page 2")
        frame_name: Имя фрейма (например "marktplaats2_nl")
    
    Returns:
        (template_json, frame_img, frame_node, use_cache)
        - template_json: dict - JSON структура из Figma
        - frame_img: PIL.Image - изображение фрейма (уже загружено из кэша если доступно)
        - frame_node: dict - узел фрейма из JSON
        - use_cache: bool - был ли использован кэш
    """
    cache = FigmaCache(service_name)
    use_cache = cache.exists()
    
    if use_cache:
        logger.info(f"📦 Используем кэш для {service_name}")
        try:
            template_json, frame_img = cache.load()
            frame_node = find_node(template_json, page, frame_name)
            
            if not frame_node:
                logger.warning(f"⚠️  Фрейм {frame_name} не найден в кэше, переключаемся на Figma API")
                use_cache = False
            else:
                return template_json, frame_img, frame_node, True
                
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки кэша для {service_name}: {e}")
            logger.info("🌐 Переключаемся на Figma API")
            use_cache = False
    
    # Fallback на Figma API
    if not use_cache:
        logger.info(f"🌐 Кэш не найден, запрос к Figma API для {service_name}")
        template_json = get_template_json(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY)
        frame_node = find_node(template_json, page, frame_name)
        
        # frame_img будет загружен позже через get_frame_image()
        return template_json, None, frame_node, False


def get_frame_image(frame_node: dict, frame_img_cached, use_cache: bool) -> Image.Image:
    """
    Получить frame_img либо из кэша либо экспортировать из Figma
    
    Args:
        frame_node: Узел фрейма из JSON
        frame_img_cached: Кэшированное изображение (может быть None)
        use_cache: Флаг использования кэша
    
    Returns:
        PIL.Image - изображение фрейма
    """
    if use_cache and frame_img_cached is not None:
        return frame_img_cached
    else:
        logger.info(f"🖼️  Экспортируем PNG из Figma для фрейма {frame_node['name']}")
        frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])
        return Image.open(io.BytesIO(frame_png)).convert("RGBA")
