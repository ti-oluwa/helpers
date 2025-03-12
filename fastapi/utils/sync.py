import asyncio
import functools
import typing
from starlette.concurrency import run_in_threadpool

from typing_extensions import ParamSpec
import uvloop


_P = ParamSpec("_P")
_R = typing.TypeVar("_R")
Function = typing.Callable[_P, _R]
CoroutineFunction = typing.Callable[_P, typing.Coroutine[typing.Any, typing.Any, _R]]


def sync_to_async(func: Function[_P, _R]) -> CoroutineFunction[_P, _R]:
    """
    Adapts a synchronous function to an asynchronous function.

    Using starlette's `run_in_threadpool` to run the synchronous function in a threadpool.
    """

    @functools.wraps(func)
    async def _wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        return await run_in_threadpool(func, *args, **kwargs)

    return _wrapper


def async_to_sync(func: CoroutineFunction[_P, _R]) -> Function[_P, _R]:
    """
    Adapts an asynchronous function to a synchronous function.

    This is useful for testing purposes.
    """

    @functools.wraps(func)
    def _wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(func(*args, **kwargs))
    
    return _wrapper
