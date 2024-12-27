from helpers.dependencies import deps_required

deps_required({"cachetools": "cachetools"})

import functools
import typing
import threading
from typing_extensions import ParamSpec
from cachetools import TTLCache, TLRUCache
import asyncio

from helpers.generics.typing import Function, CoroutineFunction

P = ParamSpec("P")
R = typing.TypeVar("R")


@typing.overload
def ttl_cache(
    func: typing.Optional[Function[P, R]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
) -> typing.Union[
    typing.Callable[[Function[P, R]], Function[P, R]], Function[P, R]
]: ...


@typing.overload
def ttl_cache(
    func: typing.Optional[CoroutineFunction[P, R]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
) -> typing.Union[
    typing.Callable[[CoroutineFunction[P, R]], CoroutineFunction[P, R]],
    CoroutineFunction[P, R],
]: ...


def ttl_cache(
    func: typing.Optional[typing.Union[Function[P, R], CoroutineFunction[P, R]]] = None,
    *,
    maxsize: int = 128,
    ttl: float = 3600,
):
    """
    Time to Live (TTL) cache decorator supporting both sync and async functions.

    :param maxsize: The maximum size of the cache.
    :param ttl: The time to live of the cache in seconds. Defaults to 1 hour.
    """
    cache = TTLCache(maxsize=maxsize, ttl=ttl)

    def decorator(
        func: typing.Union[Function[P, R], CoroutineFunction[P, R]],
    ) -> typing.Union[Function[P, R], CoroutineFunction[P, R]]:
        if asyncio.iscoroutinefunction(func):
            lock = asyncio.Lock()

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    async with lock:  # For thread safety
                        cache[key] = await func(*args, **kwargs)
                return cache[key]
        else:
            lock = threading.Lock()

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    with lock:  # For thread safety
                        cache[key] = func(*args, **kwargs)
                return cache[key]

        return functools.update_wrapper(wrapper, func)

    if func is None:
        return decorator
    return decorator(func)


@typing.overload
def lru_cache(
    func: typing.Optional[Function[P, R]] = None, *, maxsize: int = 128
) -> typing.Union[
    typing.Callable[[Function[P, R]], Function[P, R]], Function[P, R]
]: ...


@typing.overload
def lru_cache(
    func: typing.Optional[CoroutineFunction[P, R]] = None, *, maxsize: int = 128
) -> typing.Union[
    typing.Callable[[CoroutineFunction[P, R]], CoroutineFunction[P, R]],
    CoroutineFunction[P, R],
]: ...


def lru_cache(
    func: typing.Optional[typing.Union[Function[P, R], CoroutineFunction[P, R]]] = None,
    *,
    maxsize: int = 128,
):
    """
    Least Recently Used (LRU) cache decorator supporting both sync and async functions.

    :param maxsize: The maximum size of the cache.
    """
    cache = TLRUCache(maxsize=maxsize)

    def decorator(
        func: typing.Union[Function[P, R], CoroutineFunction[P, R]],
    ) -> typing.Union[Function[P, R], CoroutineFunction[P, R]]:
        if asyncio.iscoroutinefunction(func):
            lock = asyncio.Lock()

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    async with lock:  # For thread safety
                        cache[key] = await func(*args, **kwargs)
                return cache[key]
        else:
            lock = threading.Lock()

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    with lock:  # For thread safety
                        cache[key] = func(*args, **kwargs)
                return cache[key]

        return functools.update_wrapper(wrapper, func)

    if func is None:
        return decorator
    return decorator(func)
