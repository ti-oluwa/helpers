from helpers.dependencies import deps_required

deps_required({"cachetools": "cachetools"})

import functools
import typing
from typing_extensions import ParamSpec
from cachetools import TTLCache, TLRUCache
import asyncio

P = ParamSpec("P")
R = typing.TypeVar("R")


_CoroutineFunc = typing.Callable[P, typing.Coroutine[typing.Any, typing.Any, R]]
_Func = typing.Callable[P, R]


@typing.overload
def ttl_cache(
    func: _Func[P, R] = None, *, maxsize: int = 128, ttl: float = 3600
) -> typing.Union[typing.Callable[[_Func[P, R]], _Func[P, R]], _Func[P, R]]: ...


@typing.overload
def ttl_cache(
    func: _CoroutineFunc[P, R] = None, *, maxsize: int = 128, ttl: float = 3600
) -> typing.Union[
    typing.Callable[[_CoroutineFunc[P, R]], _CoroutineFunc[P, R]], _CoroutineFunc[P, R]
]: ...


def ttl_cache(
    func: typing.Optional[typing.Union[_Func[P, R], _CoroutineFunc[P, R]]] = None,
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
        func: typing.Union[_Func[P, R], _CoroutineFunc[P, R]],
    ) -> typing.Union[_Func[P, R], _CoroutineFunc[P, R]]:
        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    cache[key] = await func(*args, **kwargs)
                return cache[key]
        else:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    cache[key] = func(*args, **kwargs)
                return cache[key]

        return functools.update_wrapper(wrapper, func)

    if func is None:
        return decorator
    return decorator(func)


@typing.overload
def lru_cache(
    func: _Func[P, R] = None, *, maxsize: int = 128
) -> typing.Union[typing.Callable[[_Func[P, R]], _Func[P, R]], _Func[P, R]]: ...


@typing.overload
def lru_cache(
    func: _CoroutineFunc[P, R] = None, *, maxsize: int = 128
) -> typing.Union[
    typing.Callable[[_CoroutineFunc[P, R]], _CoroutineFunc[P, R]], _CoroutineFunc[P, R]
]: ...


def lru_cache(
    func: typing.Optional[typing.Union[_Func[P, R], _CoroutineFunc[P, R]]] = None,
    *,
    maxsize: int = 128,
):
    """
    Least Recently Used (LRU) cache decorator supporting both sync and async functions.

    :param maxsize: The maximum size of the cache.
    """
    cache = TLRUCache(maxsize=maxsize)

    def decorator(
        func: typing.Union[_Func[P, R], _CoroutineFunc[P, R]],
    ) -> typing.Union[_Func[P, R], _CoroutineFunc[P, R]]:
        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    cache[key] = await func(*args, **kwargs)
                return cache[key]
        else:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                key = (args, frozenset(kwargs.items()))
                if key not in cache:
                    cache[key] = func(*args, **kwargs)
                return cache[key]

        return functools.update_wrapper(wrapper, func)

    if func is None:
        return decorator
    return decorator(func)
