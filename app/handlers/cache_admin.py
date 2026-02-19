# app/handlers/cache_admin.py
"""
Админ-команды для управления кэшем Figma
"""
import logging
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from app.config import CFG
from app.cache.figma_cache import (
    FigmaCache,
    get_all_cached_services,
    clear_all_cache
)
from app.cache.services_config import SERVICES_CONFIG, get_all_services, get_services_by_group
from app.services.figma import get_headers, find_node
from app.handlers.menu import start as show_main_menu

logger = logging.getLogger(__name__)

# Список админов (user_id)
ADMIN_IDS = [int(x) for x in CFG.ADMIN_IDS] if hasattr(CFG, 'ADMIN_IDS') else []


def is_admin(user_id: int) -> bool:
    """Проверка прав админа"""
    return user_id in ADMIN_IDS


async def refresh_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /refresh_cache - обновление кэша Figma
    Использование: /refresh_cache [service]
    Примеры:
        /refresh_cache depop_au  - обновить только Depop
        /refresh_cache all       - обновить все сервисы (будущее)
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещен. Только для администраторов.")
        return
    
    # Получаем аргумент (имя сервиса)
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "❓ Использование: /refresh_cache <service>\n\n"
            "Доступные сервисы:\n"
            "  • depop_au - Depop (Australia)\n"
            "\nПример: /refresh_cache depop_au"
        )
        return
    
    service = args[0].lower()
    
    if service == "depop_au":
        await refresh_depop_cache(update, context)
    else:
        await update.message.reply_text(
            f"❌ Неизвестный сервис: {service}\n\n"
            "Доступные сервисы: depop_au"
        )


async def refresh_depop_cache(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновление кэша для Depop"""
    msg = await update.message.reply_text("🔄 Обновляю кэш Depop (AU)...")
    
    try:
        # Figma настройки для Depop
        FIGMA_API_URL = 'https://api.figma.com/v1'
        FIGMA_PAT = 'figd_dG6hrm0ysjdpJDGcGio2T6uJw45GPTKJGzFPvd3z'
        TEMPLATE_FILE_KEY = '76mcmHxmZ5rhQSY02Kw5pn'
        
        logger.info("📥 Запрос структуры Figma...")
        
        # Получаем структуру
        headers = {'X-FIGMA-TOKEN': FIGMA_PAT}
        response = requests.get(
            f'{FIGMA_API_URL}/files/{TEMPLATE_FILE_KEY}',
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        file_json = response.json()
        
        logger.info("✅ Структура получена")
        
        # Находим фрейм
        frame_name = 'depop1_au'
        frame_node = find_node(file_json, 'Page 2', frame_name)
        
        if not frame_node:
            raise ValueError(f"Фрейм '{frame_name}' не найден в Figma")
        
        logger.info(f"✅ Фрейм '{frame_name}' найден")
        
        # Экспортируем PNG
        await msg.edit_text("🔄 Экспортирую PNG шаблон...")
        
        scale = 2
        url = f'{FIGMA_API_URL}/images/{TEMPLATE_FILE_KEY}?ids={frame_node["id"]}&format=png&scale={scale}'
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        png_url = response.json()['images'][frame_node['id']]
        logger.info(f"📥 Скачивание PNG: {png_url}")
        
        png_response = requests.get(png_url, timeout=60)
        png_response.raise_for_status()
        template_bytes = png_response.content
        
        logger.info(f"✅ PNG получен ({len(template_bytes)} bytes)")
        
        # Сохраняем в кэш
        await msg.edit_text("💾 Сохраняю в кэш...")
        
        cache = FigmaCache("depop_au")
        cache.save(file_json, template_bytes)
        
        cache_info = cache.get_info()
        total_mb = cache_info['total_size'] / (1024 * 1024)
        
        await msg.edit_text(
            f"✅ Кэш Depop (AU) обновлен!\n\n"
            f"📊 Размер: {total_mb:.2f} MB\n"
            f"📁 Structure: {cache_info['structure_size'] / 1024:.1f} KB\n"
            f"🖼️ Template: {cache_info['template_size'] / 1024:.1f} KB\n\n"
            f"Теперь можно использовать /depop для генерации!"
        )
        
        logger.info(f"✅ Кэш Depop успешно обновлен")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка сети: {e}")
        await msg.edit_text(
            f"❌ Ошибка при запросе к Figma API:\n{str(e)}\n\n"
            "Проверьте интернет-соединение и токен Figma."
        )
        
    except Exception as e:
        logger.exception("❌ Ошибка обновления кэша")
        await msg.edit_text(
            f"❌ Ошибка обновления кэша:\n{str(e)}"
        )


async def cache_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /cache_status - статус кэша
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    services = get_all_cached_services()
    
    if not services:
        await update.message.reply_text(
            "📭 Кэш пуст.\n\n"
            "Используйте /refresh_cache для создания кэша."
        )
        return
    
    status_text = "📊 Статус кэша:\n\n"
    
    for service in services:
        name = service['name']
        info = service['info']
        total_mb = info['total_size'] / (1024 * 1024)
        
        status_text += f"✅ {name}\n"
        status_text += f"   Размер: {total_mb:.2f} MB\n\n"
    
    await update.message.reply_text(status_text)


async def clear_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /clear_cache - очистка кэша
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    try:
        count = clear_all_cache()
        await update.message.reply_text(
            f"🗑️ Кэш очищен!\n\n"
            f"Удалено сервисов: {count}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def refresh_service_cache(service_name: str, msg=None) -> tuple[bool, str]:
    """
    Универсальная функция обновления кэша для любого сервиса
    
    Returns:
        (success, message)
    """
    config = SERVICES_CONFIG.get(service_name)
    
    if not config:
        return False, f"❌ Неизвестный сервис: {service_name}"
    
    try:
        if msg:
            await msg.edit_text(f"🔄 Кэширование {config['display_name']}...")
        
        logger.info(f"📥 Кэширование {service_name}...")
        
        # Figma API настройки
        FIGMA_API_URL = 'https://api.figma.com/v1'
        headers = {'X-FIGMA-TOKEN': CFG.FIGMA_PAT}
        
        # Получаем структуру файла
        response = requests.get(
            f'{FIGMA_API_URL}/files/{CFG.TEMPLATE_FILE_KEY}',
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        file_json = response.json()
        
        # Находим фрейм
        frame_node = find_node(file_json, config['page'], config['frame'])
        
        if not frame_node:
            return False, f"❌ Фрейм '{config['frame']}' не найден на странице '{config['page']}'"
        
        # Экспортируем PNG
        scale = config.get('scale', 2)
        url = f'{FIGMA_API_URL}/images/{CFG.TEMPLATE_FILE_KEY}?ids={frame_node["id"]}&format=png&scale={scale}'
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        png_url = response.json()['images'][frame_node['id']]
        
        png_response = requests.get(png_url, timeout=60)
        png_response.raise_for_status()
        template_bytes = png_response.content
        
        # Сохраняем в кэш
        cache = FigmaCache(service_name)
        cache.save(file_json, template_bytes)
        
        cache_info = cache.get_info()
        size_kb = cache_info['total_size'] / 1024
        
        logger.info(f"✅ Кэш {service_name} обновлен ({size_kb:.1f} KB)")
        
        return True, f"✅ {config['display_name']} ({size_kb:.1f} KB)"
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка сети для {service_name}: {e}")
        return False, f"❌ {config['display_name']}: Ошибка сети"
        
    except Exception as e:
        logger.exception(f"❌ Ошибка кэширования {service_name}")
        return False, f"❌ {config['display_name']}: {str(e)[:50]}"


async def cache_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /cache_all - кэширование всех сервисов
    """
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    services = get_all_services()
    total = len(services)
    
    msg = await update.message.reply_text(
        f"🔄 Начинаю кэширование всех сервисов...\n\n"
        f"Всего сервисов: {total}\n"
        f"Это займет ~{total * 3} секунд"
    )
    
    failed: list[str] = []
    success_count = 0

    # Кэшируем каждый сервис
    for i, service_name in enumerate(services, 1):
        config = SERVICES_CONFIG[service_name]

        await msg.edit_text(
            f"🔄 Кэширование ({i}/{total})...\n\n"
            f"Текущий: {config['display_name']}"
        )

        success, message = await refresh_service_cache(service_name)

        if success:
            success_count += 1
        else:
            failed.append(message)

        # Небольшая пауза чтобы не перегружать API
        if i < total:
            await asyncio.sleep(2)

    failed_count = len(failed)

    # Финальный отчет: по запросу — показываем только ошибки
    report = (
        f"📊 Кэширование завершено!\n\n"
        f"✅ Успешно: {success_count}/{total}\n"
        f"❌ Ошибок: {failed_count}/{total}\n\n"
    )

    if not failed:
        report += "✅ Ошибок нет."
        await msg.edit_text(report)
        logger.info(f"✅ Массовое кэширование завершено: {success_count} успешно, {failed_count} ошибок")
        return

    report += "❌ Ошибки (показываю только проблемные):\n"

    # Telegram лимит ~4096 символов. Оставим запас.
    limit = 3500
    out_lines = []
    used = len(report)
    remaining = 0
    for m in failed:
        line = f"  {m}"
        if used + len(line) + 1 > limit:
            remaining += 1
            continue
        out_lines.append(line)
        used += len(line) + 1

    report += "\n".join(out_lines)
    if remaining > 0:
        report += f"\n  ... и еще {remaining} ошибок"

    await msg.edit_text(report)

    logger.info(f"✅ Массовое кэширование завершено: {success_count} успешно, {failed_count} ошибок")


def _cache_menu_text() -> tuple[str, InlineKeyboardMarkup]:
    cached_services = get_all_cached_services()
    cached_names = {s['name'] for s in cached_services}
    all_services = get_all_services()

    text = (
        f"💾 <b>Управление кэшем Figma</b>\n\n"
        f"📊 Закэшировано: {len(cached_names)}/{len(all_services)} сервисов\n\n"
        f"Выберите действие:"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Кэшировать ВСЕ сервисы", callback_data="CACHE:ALL")],
        [InlineKeyboardButton("🔄 Кэшировать сервис", callback_data="CACHE:CACHE_LIST")],
        [InlineKeyboardButton("🗑️ Очистить ВЕСЬ кэш", callback_data="CACHE:CLEAR")],
        [InlineKeyboardButton("🗑️ Очистить кэш сервиса", callback_data="CACHE:CLEAR_LIST")],
        [InlineKeyboardButton("📊 Статус кэша", callback_data="CACHE:STATUS")],
        [
            InlineKeyboardButton("⬅️ Назад", callback_data="CACHE:BACK"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="MENU"),
        ],
    ]
    return text, InlineKeyboardMarkup(keyboard)


def _service_group(service_name: str) -> str:
    if service_name.startswith("2dehands"):
        return "2dehands"
    if service_name.startswith("2ememain"):
        return "2ememain"
    if "_" in service_name:
        return service_name.split("_", 1)[0]
    return service_name


def _service_groups_keyboard(prefix: str) -> InlineKeyboardMarkup:
    groups = sorted({_service_group(s) for s in get_all_services()})
    rows = []
    for grp in groups:
        rows.append([InlineKeyboardButton(grp, callback_data=f"CACHE:{prefix}:{grp}")])

    rows.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="CACHE:MENU"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="MENU"),
    ])
    return InlineKeyboardMarkup(rows)


async def cache_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cache_menu - меню управления кэшем"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Доступ запрещен.")
        return

    text, markup = _cache_menu_text()
    await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def cache_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback от меню кэша"""
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.edit_message_text("⛔ Доступ запрещен.")
        return

    data = query.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else "MENU"

    if action in ("MENU", "BACK"):
        text, markup = _cache_menu_text()
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")

    elif action == "CACHE_LIST":
        await query.edit_message_text(
            "🔄 Выберите ГРУППУ сервиса для кэширования:",
            reply_markup=_service_groups_keyboard("CACHE_GROUP"),
        )

    elif action == "CLEAR_LIST":
        await query.edit_message_text(
            "🗑️ Выберите ГРУППУ сервиса для очистки кэша:",
            reply_markup=_service_groups_keyboard("CLEAR_GROUP"),
        )

    elif action == "CACHE_GROUP" and len(parts) >= 3:
        group = parts[2]
        service_names = [s for s in get_all_services() if _service_group(s) == group]
        if not service_names:
            text, markup = _cache_menu_text()
            await query.edit_message_text(
                f"❌ Группа не найдена: {group}\n\n{text}",
                reply_markup=markup,
                parse_mode="HTML",
            )
            return

        await query.edit_message_text(f"🔄 Кэширование группы: {group}...")

        failed: list[str] = []
        success_count = 0
        total = len(service_names)

        for i, service_name in enumerate(service_names, 1):
            cfg = SERVICES_CONFIG.get(service_name, {})
            await query.edit_message_text(
                f"🔄 Кэширование группы {group} ({i}/{total})...\n\n"
                f"Текущий: {cfg.get('display_name', service_name)}"
            )
            ok, message = await refresh_service_cache(service_name)
            if ok:
                success_count += 1
            else:
                failed.append(message)
            if i < total:
                await asyncio.sleep(1)

        result = (
            f"✅ Группа {group}: {success_count}/{total} успешно\n"
            f"❌ Ошибок: {len(failed)}"
        )
        if failed:
            result += "\n" + "\n".join(failed[:10])

        text, markup = _cache_menu_text()
        await query.edit_message_text(
            f"{result}\n\n{text}",
            reply_markup=markup,
            parse_mode="HTML",
        )

    elif action == "CLEAR_GROUP" and len(parts) >= 3:
        group = parts[2]
        service_names = [s for s in get_all_services() if _service_group(s) == group]
        if not service_names:
            text, markup = _cache_menu_text()
            await query.edit_message_text(
                f"❌ Группа не найдена: {group}\n\n{text}",
                reply_markup=markup,
                parse_mode="HTML",
            )
            return

        cleared = 0
        errors = []
        for service_name in service_names:
            try:
                FigmaCache(service_name).clear()
                cleared += 1
            except Exception as e:
                errors.append(f"{service_name}: {e}")

        result = f"🗑️ Группа {group}: очищено {cleared}/{len(service_names)}"
        if errors:
            result += "\n" + "\n".join(errors[:10])

        text, markup = _cache_menu_text()
        await query.edit_message_text(
            f"{result}\n\n{text}",
            reply_markup=markup,
            parse_mode="HTML",
        )

    elif action == "ALL":
        await query.edit_message_text("🔄 Запускаю кэширование всех сервисов...")

        services = get_all_services()
        total = len(services)
        failed: list[str] = []
        success_count = 0

        for i, service_name in enumerate(services, 1):
            config = SERVICES_CONFIG[service_name]

            await query.edit_message_text(
                f"🔄 Кэширование ({i}/{total})...\n\n"
                f"Текущий: {config['display_name']}"
            )

            success, message = await refresh_service_cache(service_name)
            if success:
                success_count += 1
            else:
                failed.append(message)

            if i < total:
                await asyncio.sleep(2)

        failed_count = len(failed)
        report = (
            f"📊 Кэширование завершено!\n\n"
            f"✅ Успешно: {success_count}/{total}\n"
            f"❌ Ошибок: {failed_count}/{total}\n\n"
        )

        if not failed:
            report += "✅ Ошибок нет."
        else:
            report += "❌ Ошибки (показываю только проблемные):\n"
            limit = 3500
            out_lines = []
            used = len(report)
            remaining = 0
            for m in failed:
                line = f"  {m}"
                if used + len(line) + 1 > limit:
                    remaining += 1
                    continue
                out_lines.append(line)
                used += len(line) + 1

            report += "\n".join(out_lines)
            if remaining > 0:
                report += f"\n  ... и еще {remaining} ошибок"

        text, markup = _cache_menu_text()
        await query.edit_message_text(
            f"{report}\n\n{text}",
            reply_markup=markup,
            parse_mode="HTML",
        )

    elif action == "STATUS":
        services = get_all_cached_services()

        if not services:
            await query.edit_message_text(
                "📭 Кэш пуст.\n\nИспользуйте кнопки кэширования в этом меню.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Назад", callback_data="CACHE:MENU"),
                     InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")]
                ]),
            )
            return

        groups = get_services_by_group()
        status_text = "📊 <b>Статус кэша:</b>\n\n"

        for group_name, service_names in groups.items():
            cached_in_group = [s for s in services if s['name'] in service_names]
            if cached_in_group:
                status_text += f"<b>{group_name}:</b>\n"
                for service in cached_in_group:
                    size_kb = service['info']['total_size'] / 1024
                    config = SERVICES_CONFIG[service['name']]
                    status_text += f"  ✅ {config['display_name']} ({size_kb:.1f} KB)\n"
                status_text += "\n"

        total_size = sum(s['info']['total_size'] for s in services) / (1024 * 1024)
        status_text += f"💾 <b>Всего:</b> {len(services)} сервисов, {total_size:.2f} MB"

        await query.edit_message_text(
            status_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="CACHE:MENU"),
                 InlineKeyboardButton("🏠 Главное меню", callback_data="MENU")]
            ]),
        )

    elif action == "CLEAR":
        try:
            count = clear_all_cache()
            result = f"🗑️ Кэш очищен!\n\nУдалено сервисов: {count}"
        except Exception as e:
            result = f"❌ Ошибка: {e}"

        text, markup = _cache_menu_text()
        await query.edit_message_text(
            f"{result}\n\n{text}",
            reply_markup=markup,
            parse_mode="HTML",
        )


# Регистрация handlers
def get_cache_handlers():
    """Получить список handlers для кэша"""
    return [
        CommandHandler("refresh_cache", refresh_cache_command),
        CommandHandler("cache_status", cache_status_command),
        CommandHandler("clear_cache", clear_cache_command),
        CommandHandler("cache_all", cache_all_command),
        CommandHandler("cache_menu", cache_menu_command),
        CallbackQueryHandler(cache_menu_callback, pattern=r"^CACHE:")
    ]
