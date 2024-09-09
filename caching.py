import functools
from typing import Callable, TypeVar, Coroutine, Any
from cachetools import TTLCache
import asyncio
import threading

T = TypeVar("T")


class SyncTTLCache:
    """Thread-safe implementation of `cachetools.TTLCache`"""

    def __init__(self, **kwargs):
        self.cache = TTLCache(**kwargs)
        self.lock = threading.Lock()

    def __getitem__(self, key):
        with self.lock:
            return self.cache[key]

    def __setitem__(self, key, value):
        with self.lock:
            self.cache[key] = value

    def __delitem__(self, key):
        with self.lock:
            del self.cache[key]

    def __contains__(self, key):
        with self.lock:
            return key in self.cache

    def get(self, key, default=None):
        with self.lock:
            return self.cache.get(key, default)

    def pop(self, key, default=None):
        with self.lock:
            return self.cache.pop(key, default)

    def clear(self):
        with self.lock:
            self.cache.clear()


class AsyncTTLCache:
    """Asynchronous thread-safe implementation of `cachetools.TTLCache`"""

    def __init__(self, **kwargs):
        self.cache = TTLCache(**kwargs)
        self.lock = asyncio.Lock()

    async def __getitem__(self, key):
        async with self.lock:
            return self.cache[key]

    async def __setitem__(self, key, value):
        async with self.lock:
            self.cache[key] = value

    async def __delitem__(self, key):
        async with self.lock:
            del self.cache[key]

    async def __contains__(self, key):
        async with self.lock:
            return key in self.cache

    async def get(self, key, default=None):
        async with self.lock:
            return self.cache.get(key, default)

    async def pop(self, key, default=None):
        async with self.lock:
            return self.cache.pop(key, default)

    async def clear(self):
        async with self.lock:
            self.cache.clear()


def async_ttl_cache(
    coroutine_func: Callable[..., Coroutine[Any, Any, T]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
):
    """
    Cache the result of the decorated asynchronous function's
    call for a specified amount of time

    :param maxsize: The maximum size of the cache
    :param ttl: The time to live of the cache in seconds. Defaults to 1 hour.
    """
    cache = AsyncTTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(
        coroutine_func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(coroutine_func)
        async def wrapper(*args, **kwargs) -> Coroutine[Any, Any, T]:
            key = (args, frozenset(kwargs.items()))
            if key not in cache:
                result = await coroutine_func(*args, **kwargs)
                cache[key] = result
            return cache[key]

        return wrapper

    if coroutine_func is None:
        return decorator
    return decorator(coroutine_func)


def ttl_cache(func: Callable[..., T] = None, *, maxsize: int = 128, ttl: float = 3600):
    """
    Cache the result of the decorated function's call for a specified amount of time

    :param maxsize: The maximum size of the cache
    :param ttl: The time to live of the cache in seconds. Defaults to 1 hour.
    """
    cache = SyncTTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            key = (args, frozenset(kwargs.items()))
            if key not in cache:
                result = func(*args, **kwargs)
                cache[key] = result
            return cache[key]

        return wrapper

    if func is None:
        return decorator
    return decorator(func)
