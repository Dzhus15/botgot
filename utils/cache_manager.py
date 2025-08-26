"""
Центральный менеджер кэша для оптимизации производительности
"""
import time
from typing import Any, Dict, Optional, TypeVar, Generic
import asyncio
from functools import wraps

T = TypeVar('T')

class CacheManager(Generic[T]):
    """Универсальный менеджер кэша с TTL"""
    
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        """Проверить, истек ли кэш"""
        return time.time() - entry['timestamp'] > entry['ttl']
    
    async def get(self, key: str) -> Optional[T]:
        """Получить значение из кэша"""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                if not self._is_expired(entry):
                    return entry['value']
                else:
                    # Удалить истекшую запись
                    del self.cache[key]
            return None
    
    async def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Установить значение в кэш"""
        async with self._lock:
            self.cache[key] = {
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl or self.default_ttl
            }
    
    async def delete(self, key: str) -> None:
        """Удалить значение из кэша"""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
    
    async def clear(self) -> None:
        """Очистить весь кэш"""
        async with self._lock:
            self.cache.clear()
    
    async def cleanup_expired(self) -> int:
        """Очистить истекшие записи и вернуть количество удаленных"""
        expired_keys = []
        async with self._lock:
            for key, entry in self.cache.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
        
        return len(expired_keys)
    
    def size(self) -> int:
        """Размер кэша"""
        return len(self.cache)


def cached(ttl: int = 300, key_prefix: str = ""):
    """Декоратор для кэширования результатов функций"""
    def decorator(func):
        cache = CacheManager(ttl)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Создать ключ на основе аргументов
            cache_key = f"{key_prefix}{func.__name__}_{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Попробовать получить из кэша
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Выполнить функцию и кэшировать результат
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result)
            return result
        
        # Добавить методы управления кэшем к функции
        wrapper.cache_clear = cache.clear
        wrapper.cache_info = lambda: {"size": cache.size()}
        
        return wrapper
    return decorator


# Глобальные экземпляры кэша
user_cache = CacheManager(ttl=300)  # 5 минут для пользователей
stats_cache = CacheManager(ttl=600)  # 10 минут для статистики