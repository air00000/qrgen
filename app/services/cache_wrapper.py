# app/services/cache_wrapper.py
"""
Обёртки для функций генерации с автоматическим использованием кэша.
Уровни кэширования (от быстрого к медленному):
  1. _MEM_CACHE  — словарь в памяти процесса (мгновенно)
  2. FigmaCache  — JSON + PNG на диске (миллисекунды)
  3. Figma API   — HTTP запросы (секунды)
"""
import logging
from PIL import Image
import io

from app.cache.figma_cache import FigmaCache
from app.services.figma import get_template_json, find_node, export_frame_as_png
from app.config import CFG

logger = logging.getLogger(__name__)

# ── In-memory кэш: { service_name: (template_json, frame_img) } ──────────────
_MEM_CACHE: dict = {}


def _mem_get(service_name: str):
    return _MEM_CACHE.get(service_name)


def _mem_set(service_name: str, template_json: dict, frame_img: Image.Image):
    _MEM_CACHE[service_name] = (template_json, frame_img)


def _mem_clear(service_name: str = None):
    """Инвалидировать память (весь кэш или конкретный сервис)."""
    if service_name:
        _MEM_CACHE.pop(service_name, None)
    else:
        _MEM_CACHE.clear()
# ─────────────────────────────────────────────────────────────────────────────


def load_template_with_cache(service_name: str, page: str, frame_name: str,
                              figma_pat: str = None, file_key: str = None):
    """
    Загрузить template_json и frame_img.
    Порядок: memory → disk cache → Figma API.
    """
    pat = figma_pat or CFG.FIGMA_PAT
    fkey = file_key or CFG.TEMPLATE_FILE_KEY

    # 1. Memory
    mem = _mem_get(service_name)
    if mem is not None:
        template_json, frame_img = mem
        frame_node = find_node(template_json, page, frame_name)
        if frame_node:
            logger.debug(f"⚡ Memory-кэш hit: {service_name}")
            return template_json, frame_img, frame_node, True

    # 2. Disk cache
    cache = FigmaCache(service_name)
    if cache.exists():
        try:
            template_json, frame_img = cache.load()
            frame_node = find_node(template_json, page, frame_name)
            if frame_node:
                logger.info(f"📦 Disk-кэш hit: {service_name}")
                _mem_set(service_name, template_json, frame_img)
                return template_json, frame_img, frame_node, True
            else:
                logger.warning(f"⚠️  Фрейм {frame_name} не найден в disk-кэше {service_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка disk-кэша {service_name}: {e}")

    # 3. Figma API fallback
    logger.info(f"🌐 Figma API запрос для {service_name}")
    template_json = get_template_json(pat, fkey)
    frame_node = find_node(template_json, page, frame_name)
    return template_json, None, frame_node, False


def get_frame_image(frame_node: dict, frame_img_cached, use_cache: bool,
                    figma_pat: str = None, file_key: str = None) -> Image.Image:
    """
    Получить frame_img: из кэша или экспортировать из Figma.
    """
    if use_cache and frame_img_cached is not None:
        return frame_img_cached
    else:
        pat = figma_pat or CFG.FIGMA_PAT
        fkey = file_key or CFG.TEMPLATE_FILE_KEY
        logger.info(f"🖼️  Экспорт PNG из Figma: {frame_node['name']}")
        frame_png = export_frame_as_png(pat, fkey, frame_node["id"])
        return Image.open(io.BytesIO(frame_png)).convert("RGBA")

