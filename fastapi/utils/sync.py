import functools
import typing
from starlette.concurrency import run_in_threadpool

from typing_extensions import ParamSpec


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
