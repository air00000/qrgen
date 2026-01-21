#!/usr/bin/env python3
"""
Скрипт для обновления всех сервисов на использование кэша
"""

import re

# Файл для обновления
PDF_FILE = "app/services/pdf.py"
SUBITO_VARIANTS_FILE = "app/services/subito_variants.py"
TWODEHANDS_FILE = "app/services/twodehands.py"
KLEIZE_FILE = "app/services/kleize.py"
CONTO_FILE = "app/services/conto.py"

def update_pdf_services():
    """Обновить сервисы в pdf.py"""
    
    with open(PDF_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Заменяем импорт get_template_json на load_from_cache_or_figma
    if 'from app.cache.cache_helper import load_from_cache_or_figma' not in content:
        content = content.replace(
            'from app.cache.figma_cache import FigmaCache',
            'from app.cache.figma_cache import FigmaCache\nfrom app.cache.cache_helper import load_from_cache_or_figma'
        )
    
    # Marktplaats
    content = re.sub(
        r'def create_image_marktplaats\([^)]+\) -> bytes:\s+"""[^"]+"""\s+template_json = get_template_json\([^)]+\)',
        lambda m: m.group(0).replace(
            'template_json = get_template_json(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY)',
            'template_json, template_img = load_from_cache_or_figma("marktplaats", "Page 2", "marktplaats2_nl")'
        ),
        content
    )
    
    # Заменяем загрузку PNG для Marktplaats
    content = re.sub(
        r'# Фон из Figma\s+frame_png = export_frame_as_png\(CFG\.FIGMA_PAT, CFG\.TEMPLATE_FILE_KEY, frame_node\["id"\]\)\s+frame_img = Image\.open\(io\.BytesIO\(frame_png\)\)\.convert\("RGBA"\)\s+w = int\(frame_node\["absoluteBoundingBox"\]\["width"\] \* CFG\.SCALE_FACTOR\)\s+h = int\(frame_node\["absoluteBoundingBox"\]\["height"\] \* CFG\.SCALE_FACTOR\)\s+frame_img = frame_img\.resize\(\(w, h\), Image\.Resampling\.LANCZOS\)',
        '# Используем шаблон из кэша\n    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)\n    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)\n    frame_img = template_img.resize((w, h), Image.Resampling.LANCZOS)',
        content,
        count=1
    )
    
    # Subito
    content = re.sub(
        r'(def create_image_subito\([^)]+\) -> bytes:\s+"""[^"]+""")\s+template_json = get_template_json\([^)]+\)',
        r'\1\n    template_json, template_img = load_from_cache_or_figma("subito", "Page 2", "subito1")',
        content
    )
    
    # Заменяем загрузку PNG для Subito (все вхождения в этой функции)
    # Ищем функцию create_image_subito и заменяем в ней
    subito_start = content.find('def create_image_subito(')
    if subito_start != -1:
        # Находим конец функции (следующая def или конец файла)
        next_def = content.find('\ndef ', subito_start + 1)
        if next_def == -1:
            subito_section = content[subito_start:]
            rest = ''
        else:
            subito_section = content[subito_start:next_def]
            rest = content[next_def:]
        
        # Заменяем в этой секции
        subito_section = subito_section.replace(
            '# Фон из Figma\n    frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])\n    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")\n    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)\n    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)\n    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)',
            '# Используем шаблон из кэша\n    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)\n    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)\n    frame_img = template_img.resize((w, h), Image.Resampling.LANCZOS)'
        )
        
        content = content[:subito_start] + subito_section + rest
    
    # Wallapop
    content = re.sub(
        r'(def create_image_wallapop\([^)]+\) -> bytes:\s+"""[^"]+"""[^t]*?)template_json = get_template_json\([^)]+\)',
        r'\1template_json, template_img = load_from_cache_or_figma("wallapop", "Page 3", "wallapop1")',
        content
    )
    
    # Сохраняем
    with open(PDF_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Обновлен {PDF_FILE}")


def update_subito_variants():
    """Обновить варианты Subito"""
    
    with open(SUBITO_VARIANTS_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Добавляем импорт
    if 'from app.cache.cache_helper import load_from_cache_or_figma' not in content:
        content = content.replace(
            'from app.services.pdf import',
            'from app.cache.cache_helper import load_from_cache_or_figma\nfrom app.services.pdf import'
        )
    
    # Email Request
    content = re.sub(
        r'(def create_image_subito_email_request\([^)]+\) -> bytes:\s+"""[^"]+""")\s+template_json = get_template_json\([^)]+\)',
        r'\1\n    template_json, template_img = load_from_cache_or_figma("subito_email_request", "Page 2", "subito2")',
        content
    )
    
    # Email Confirm
    content = re.sub(
        r'(def create_image_subito_email_confirm\([^)]+\) -> bytes:\s+"""[^"]+""")\s+template_json = get_template_json\([^)]+\)',
        r'\1\n    template_json, template_img = load_from_cache_or_figma("subito_email_confirm", "Page 2", "subito3")',
        content
    )
    
    # SMS Request
    content = re.sub(
        r'(def create_image_subito_sms_request\([^)]+\) -> bytes:\s+"""[^"]+""")\s+template_json = get_template_json\([^)]+\)',
        r'\1\n    template_json, template_img = load_from_cache_or_figma("subito_sms_request", "Page 2", "subito4")',
        content
    )
    
    # SMS Confirm
    content = re.sub(
        r'(def create_image_subito_sms_confirm\([^)]+\) -> bytes:\s+"""[^"]+""")\s+template_json = get_template_json\([^)]+\)',
        r'\1\n    template_json, template_img = load_from_cache_or_figma("subito_sms_confirm", "Page 2", "subito5")',
        content
    )
    
    # Заменяем загрузку PNG во всех функциях
    content = content.replace(
        '# Фон из Figma\n    frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])\n    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")\n    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)\n    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)\n    frame_img = frame_img.resize((w, h), Image.Resampling.LANCZOS)',
        '# Используем шаблон из кэша\n    w = int(frame_node["absoluteBoundingBox"]["width"] * CFG.SCALE_FACTOR)\n    h = int(frame_node["absoluteBoundingBox"]["height"] * CFG.SCALE_FACTOR)\n    frame_img = template_img.resize((w, h), Image.Resampling.LANCZOS)'
    )
    
    with open(SUBITO_VARIANTS_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Обновлен {SUBITO_VARIANTS_FILE}")


def update_other_services():
    """Обновить остальные сервисы (twodehands, kleize, conto)"""
    
    # twodehands
    try:
        with open(TWODEHANDS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Добавляем импорт если его нет
        if 'from app.cache.cache_helper import load_from_cache_or_figma' not in content:
            content = content.replace(
                'from app.services.figma import',
                'from app.cache.cache_helper import load_from_cache_or_figma\nfrom app.services.figma import'
            )
        
        # Заменяем get_template_json на load_from_cache_or_figma
        content = re.sub(
            r'template_json = get_template_json\(CFG\.FIGMA_PAT, CFG\.TEMPLATE_FILE_KEY\)',
            'template_json, template_img = load_from_cache_or_figma("2dehands" if lang == "nl" else "2ememain", "Page 4", frame_name)',
            content
        )
        
        # Заменяем загрузку PNG
        content = content.replace(
            'frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])\n    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")',
            '# Используем шаблон из кэша'
        )
        
        with open(TWODEHANDS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Обновлен {TWODEHANDS_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка обновления {TWODEHANDS_FILE}: {e}")
    
    # kleize
    try:
        with open(KLEIZE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'from app.cache.cache_helper import load_from_cache_or_figma' not in content:
            content = content.replace(
                'from app.services.figma import',
                'from app.cache.cache_helper import load_from_cache_or_figma\nfrom app.services.figma import'
            )
        
        content = re.sub(
            r'template_json = get_template_json\(CFG\.FIGMA_PAT, CFG\.TEMPLATE_FILE_KEY\)',
            'template_json, template_img = load_from_cache_or_figma("kleize", "Page 5", "kleize1")',
            content
        )
        
        content = content.replace(
            'frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])\n    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")',
            '# Используем шаблон из кэша'
        )
        
        with open(KLEIZE_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Обновлен {KLEIZE_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка обновления {KLEIZE_FILE}: {e}")
    
    # conto
    try:
        with open(CONTO_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'from app.cache.cache_helper import load_from_cache_or_figma' not in content:
            content = content.replace(
                'from app.services.figma import',
                'from app.cache.cache_helper import load_from_cache_or_figma\nfrom app.services.figma import'
            )
        
        content = re.sub(
            r'template_json = get_template_json\(CFG\.FIGMA_PAT, CFG\.TEMPLATE_FILE_KEY\)',
            'template_json, template_img = load_from_cache_or_figma("conto", "Page 6", "conto1")',
            content
        )
        
        content = content.replace(
            'frame_png = export_frame_as_png(CFG.FIGMA_PAT, CFG.TEMPLATE_FILE_KEY, frame_node["id"])\n    frame_img = Image.open(io.BytesIO(frame_png)).convert("RGBA")',
            '# Используем шаблон из кэша'
        )
        
        with open(CONTO_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Обновлен {CONTO_FILE}")
    except Exception as e:
        print(f"⚠️ Ошибка обновления {CONTO_FILE}: {e}")


if __name__ == "__main__":
    print("🔄 Обновление сервисов для использования кэша...\n")
    
    update_pdf_services()
    update_subito_variants()
    update_other_services()
    
    print("\n✅ Все сервисы обновлены!")
    print("\nТеперь запустите /cache_all в боте для создания кэша")
