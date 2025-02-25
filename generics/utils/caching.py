from helpers.dependencies import deps_required

deps_required({"cachetools": "cachetools"})

import functools
import time
import typing
import threading
from typing_extensions import ParamSpec
from cachetools import TTLCache, TLRUCache
import asyncio

from helpers.generics.typing import Function, CoroutineFunction

P = ParamSpec("P")
R = typing.TypeVar("R")
T = typing.TypeVar("T")
_KT = typing.TypeVar("_KT")
_VT = typing.TypeVar("_VT")


class _CacheSentinel:
    """Sentinel object for cache misses."""

    def __repr__(self) -> str:
        return "<CACHE_MISS>"


CACHE_MISS = _CacheSentinel()


@typing.overload
def ttl_cache(
    func: typing.Optional[Function[P, R]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
    include_args: bool = True,
    include_kwargs: bool = True,
) -> typing.Union[
    typing.Callable[[Function[P, R]], Function[P, R]], Function[P, R]
]: ...


@typing.overload
def ttl_cache(
    func: typing.Optional[CoroutineFunction[P, R]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
    include_args: bool = True,
    include_kwargs: bool = True,
) -> typing.Union[
    typing.Callable[[CoroutineFunction[P, R]], CoroutineFunction[P, R]],
    CoroutineFunction[P, R],
]: ...


class ThreadSafeTTLCache(typing.Generic[_VT], TTLCache):
    """Thread-safe TTL Cache with better error handling."""

    def __init__(
        self,
        maxsize: int,
        ttl: float,
        timer: typing.Callable[[], float] = time.monotonic,
    ):
        super().__init__(maxsize, ttl, timer)
        self._lock = threading.RLock()

    def __getitem__(self, key: _KT) -> _VT:
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key: _KT, value: _VT) -> None:
        with self._lock:
            super().__setitem__(key, value)

    def get(
        self, key: _KT, default: typing.Optional[typing.Union[_VT, T]] = None
    ) -> typing.Optional[typing.Union[_VT, T]]:
        with self._lock:
            try:
                return self[key]
            except KeyError:
                return default


def ttl_cache(
    func: typing.Optional[typing.Union[Function[P, R], CoroutineFunction[P, R]]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
    include_args: bool = True,
    include_kwargs: bool = True,
):
    """
    Time to Live (TTL) cache decorator with advanced features.

    :param maxsize: Maximum size of the cache
    :param ttl: Time to live in seconds (default: 1 hour)
    :param include_args: Whether to include positional args in cache key
    :param include_kwargs: Whether to include keyword args in cache key
    :returns: Decorated function with caching
    :raises ValueError: If maxsize is less than 0 or ttl is not positive

    Example:
        ```python
        @ttl_cache(maxsize=100, ttl=1800)  # 30 minute cache
        def get_user(user_id: int) -> User:
            return db.query(User).get(user_id)

        @ttl_cache(maxsize=100, ttl=3600, include_kwargs=False)
        async def get_stats(*metrics: str) -> Dict[str, float]:
            return await fetch_metrics(metrics)
        ```
    """
    if maxsize < 0:
        raise ValueError("maxsize must be >= 0")
    if ttl <= 0:
        raise ValueError("ttl must be positive")

    cache = ThreadSafeTTLCache[R](maxsize=maxsize, ttl=ttl)

    def make_key(*args: P.args, **kwargs: P.kwargs) -> CacheKey:
        """Create cache key from function arguments."""
        key_parts = []
        if include_args:
            key_parts.append(args)
        if include_kwargs:
            key_parts.append(frozenset(kwargs.items()))
        return tuple(key_parts)  # type: ignore

    def decorator(
        func: typing.Union[Function[P, R], CoroutineFunction[P, R]],
    ) -> typing.Union[Function[P, R], CoroutineFunction[P, R]]:
        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = make_key(*args, **kwargs)
                result = cache.get(key, CACHE_MISS)
                if result is CACHE_MISS:
                    result = await func(*args, **kwargs)
                    cache[key] = result
                return result
        else:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = make_key(*args, **kwargs)
                result = cache.get(key, CACHE_MISS)
                if result is CACHE_MISS:
                    result = func(*args, **kwargs)
                    cache[key] = result
                return result

        wrapper.cache = cache  # type: ignore
        wrapper.cache_info = lambda: {  # type: ignore
            "maxsize": cache.maxsize,
            "currsize": len(cache),
            "ttl": cache.ttl,
            "hits": cache.hits if hasattr(cache, "hits") else 0,
            "misses": cache.misses if hasattr(cache, "misses") else 0,
        }
        return functools.update_wrapper(wrapper, func)

    if func is None:
        return decorator
    return decorator(func)


CacheKey = typing.Tuple[
    typing.Tuple[typing.Any, ...], typing.FrozenSet[typing.Tuple[str, typing.Any]]
]
TTUFunc = typing.Callable[[CacheKey, _VT, float], float]


def default_ttu(key: CacheKey, value: _VT, time: float) -> float:
    """Default TTU function that returns 1 hour."""
    return 3600.0


class ThreadSafeTLRUCache(typing.Generic[_VT], TLRUCache):
    """Thread-safe TLRU Cache with better error handling."""

    def __init__(
        self,
        maxsize: int,
        ttu: typing.Union[float, TTUFunc[_VT]],
        timer: typing.Callable[[], float] = time.monotonic,
    ):
        super().__init__(maxsize, ttu, timer)
        self._lock = threading.RLock()  # Reentrant lock for nested operations

    def __getitem__(self, key: _KT) -> _VT:
        with self._lock:
            return super().__getitem__(key)

    def __setitem__(self, key: _KT, value: _VT) -> None:
        with self._lock:
            super().__setitem__(key, value)

    def get(
        self, key: _KT, default: typing.Optional[typing.Union[_VT, T]] = None
    ) -> typing.Optional[typing.Union[_VT, T]]:
        with self._lock:
            try:
                return self[key]
            except KeyError:
                return default


def _make_ttu_func(ttu: typing.Union[float, TTUFunc[_VT]]) -> TTUFunc[_VT]:
    """Convert TTU value to a function if it's a float."""
    if isinstance(ttu, (int, float)):
        return lambda *_: float(ttu)
    return ttu


@typing.overload
def tlru_cache(
    func: typing.Optional[Function[P, R]] = None,
    *,
    maxsize: int = 128,
    ttu: typing.Union[float, TTUFunc[R]] = default_ttu,
    include_args: bool = True,
    include_kwargs: bool = True,
) -> typing.Union[
    typing.Callable[[Function[P, R]], Function[P, R]], Function[P, R]
]: ...


@typing.overload
def tlru_cache(
    func: typing.Optional[CoroutineFunction[P, R]] = None,
    *,
    maxsize: int = 128,
    ttu: typing.Union[float, TTUFunc[R]] = default_ttu,
    include_args: bool = True,
    include_kwargs: bool = True,
) -> typing.Union[
    typing.Callable[[CoroutineFunction[P, R]], CoroutineFunction[P, R]],
    CoroutineFunction[P, R],
]: ...


def tlru_cache(
    func: typing.Optional[typing.Union[Function[P, R], CoroutineFunction[P, R]]] = None,
    *,
    maxsize: int = 128,
    ttu: typing.Union[float, TTUFunc[R]] = default_ttu,
    include_args: bool = True,
    include_kwargs: bool = True,
):
    """
    Time-aware Least Recently Used (LRU) cache decorator with advanced features.

    :param maxsize: Maximum size of the cache
    :param ttu: Time to update in seconds or function(key, value, time) -> float
    :param include_args: Whether to include positional args in cache key
    :param include_kwargs: Whether to include keyword args in cache key
    :returns: Decorated function with caching
    :raises ValueError: If maxsize is less than 0

    Example:
        ```python
        # Basic usage with 1 hour TTU
        @tlru_cache(maxsize=100)
        def get_user(user_id: int) -> User:
            return db.query(User).get(user_id)

        # Custom TTU function
        def dynamic_ttu(key, value, time):
            return 3600 if isinstance(value, User) else 1800

        @tlru_cache(maxsize=100, ttu=dynamic_ttu)
        async def get_user_async(user_id: int) -> User:
            return await db.query(User).get(user_id)
        ```
    """
    if maxsize < 0:
        raise ValueError("maxsize must be >= 0")

    cache = ThreadSafeTLRUCache[R](maxsize=maxsize, ttu=_make_ttu_func(ttu))

    def make_key(*args: P.args, **kwargs: P.kwargs) -> CacheKey:
        """Create cache key from function arguments."""
        key_parts = []
        if include_args:
            key_parts.append(args)
        if include_kwargs:
            key_parts.append(frozenset(kwargs.items()))
        return tuple(key_parts)  # type: ignore

    def decorator(
        func: typing.Union[Function[P, R], CoroutineFunction[P, R]],
    ) -> typing.Union[Function[P, R], CoroutineFunction[P, R]]:
        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = make_key(*args, **kwargs)
                result = cache.get(key, CACHE_MISS)
                if result is CACHE_MISS:
                    result = await func(*args, **kwargs)
                    cache[key] = result
                return result
        else:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = make_key(*args, **kwargs)
                result = cache.get(key, CACHE_MISS)
                if result is CACHE_MISS:
                    result = func(*args, **kwargs)
                    cache[key] = result
                return result

        wrapper.cache = cache  # type: ignore
        wrapper.cache_info = lambda: {  # type: ignore
            "maxsize": cache.maxsize,
            "currsize": len(cache),
            "hits": cache.hits if hasattr(cache, "hits") else 0,
            "misses": cache.misses if hasattr(cache, "misses") else 0,
        }
        return functools.update_wrapper(wrapper, func)

    if func is None:
        return decorator
    return decorator(func)
