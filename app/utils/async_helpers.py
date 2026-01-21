# app/utils/async_helpers.py
"""
Утилиты для асинхронной работы бота
"""
import asyncio
import time
import logging
from typing import Callable, Any
from functools import wraps
from collections import defaultdict

logger = logging.getLogger(__name__)

# Rate limiting per user
class RateLimiter:
    """
    Rate limiter для ограничения количества запросов от одного пользователя
    """
    def __init__(self, max_requests: int = 5, time_window: int = 60):
        """
        Args:
            max_requests: Максимум запросов в окне
            time_window: Временное окно в секундах
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)  # user_id -> [timestamps]
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, user_id: int) -> tuple[bool, int]:
        """
        Проверяет разрешен ли запрос от пользователя
        
        Returns:
            (allowed, wait_time): allowed=True если разрешено, wait_time=секунды до следующего запроса
        """
        async with self._lock:
            now = time.time()
            
            # Очистка старых запросов
            self.requests[user_id] = [
                ts for ts in self.requests[user_id]
                if now - ts < self.time_window
            ]
            
            # Проверка лимита
            if len(self.requests[user_id]) >= self.max_requests:
                oldest = self.requests[user_id][0]
                wait_time = int(self.time_window - (now - oldest)) + 1
                return False, wait_time
            
            # Добавление нового запроса
            self.requests[user_id].append(now)
            return True, 0
    
    async def cleanup_old_entries(self):
        """Периодическая очистка старых записей"""
        while True:
            await asyncio.sleep(self.time_window * 2)
            async with self._lock:
                now = time.time()
                users_to_remove = []
                
                for user_id, timestamps in self.requests.items():
                    # Удаляем старые timestamp
                    self.requests[user_id] = [
                        ts for ts in timestamps
                        if now - ts < self.time_window
                    ]
                    # Если список пустой - помечаем пользователя на удаление
                    if not self.requests[user_id]:
                        users_to_remove.append(user_id)
                
                # Удаляем пользователей без активных запросов
                for user_id in users_to_remove:
                    del self.requests[user_id]
                
                if users_to_remove:
                    logger.info(f"🧹 Очищено {len(users_to_remove)} неактивных пользователей из rate limiter")


# Глобальный rate limiter
# 5 генераций в минуту на пользователя
rate_limiter = RateLimiter(max_requests=5, time_window=60)


def with_rate_limit(func):
    """
    Декоратор для добавления rate limiting к handler функциям
    """
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        
        allowed, wait_time = await rate_limiter.is_allowed(user_id)
        
        if not allowed:
            logger.warning(f"⚠️  Rate limit для пользователя {user_id}: ждать {wait_time}с")
            await update.message.reply_text(
                f"⏳ Слишком много запросов! Подожди {wait_time} секунд."
            )
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


async def run_in_executor(executor, func: Callable, *args, **kwargs) -> Any:
    """
    Запуск синхронной функции в executor
    
    Args:
        executor: ThreadPoolExecutor или ProcessPoolExecutor
        func: Синхронная функция
        *args, **kwargs: Аргументы функции
    
    Returns:
        Результат выполнения функции
    """
    loop = asyncio.get_event_loop()
    
    if kwargs:
        # Если есть kwargs - используем lambda
        return await loop.run_in_executor(
            executor,
            lambda: func(*args, **kwargs)
        )
    else:
        # Без kwargs - прямой вызов
        return await loop.run_in_executor(executor, func, *args)


class GenerationQueue:
    """
    Очередь генераций с ограничением параллельных задач
    """
    def __init__(self, max_concurrent: int = 10):
        """
        Args:
            max_concurrent: Максимум параллельных генераций
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        async with self._lock:
            self.active_count += 1
            logger.info(f"📊 Активных генераций: {self.active_count}")
        
        await self.semaphore.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.semaphore.release()
        
        async with self._lock:
            self.active_count -= 1
            logger.info(f"📊 Активных генераций: {self.active_count}")


# Глобальная очередь генераций
# Максимум 10 параллельных генераций
generation_queue = GenerationQueue(max_concurrent=10)


async def generate_with_queue(executor, func: Callable, *args, **kwargs) -> Any:
    """
    Генерация изображения с контролем очереди
    
    Args:
        executor: ThreadPoolExecutor
        func: Функция генерации
        *args, **kwargs: Аргументы
    
    Returns:
        Результат генерации
    """
    async with generation_queue:
        return await run_in_executor(executor, func, *args, **kwargs)


# Статистика использования
class UsageStats:
    """Статистика использования бота"""
    def __init__(self):
        self.total_requests = 0
        self.successful = 0
        self.failed = 0
        self.by_service = defaultdict(int)
        self._lock = asyncio.Lock()
    
    async def record_request(self, service: str, success: bool = True):
        """Записать запрос"""
        async with self._lock:
            self.total_requests += 1
            self.by_service[service] += 1
            
            if success:
                self.successful += 1
            else:
                self.failed += 1
    
    async def get_stats(self) -> dict:
        """Получить статистику"""
        async with self._lock:
            return {
                'total': self.total_requests,
                'successful': self.successful,
                'failed': self.failed,
                'by_service': dict(self.by_service),
                'success_rate': f"{(self.successful / max(self.total_requests, 1)) * 100:.1f}%"
            }


# Глобальная статистика
usage_stats = UsageStats()
