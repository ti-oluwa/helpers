import time
import typing
import asyncio
from typing_extensions import ParamSpec
import functools

from helpers.logging import log_exception
from helpers.generics.typing import Function, CoroutineFunction


_P = ParamSpec("_P")
_R = typing.TypeVar("_R")
_T = typing.TypeVar("_T")
_R_co = typing.TypeVar("_R_co", covariant=True)
BackOffFunction = typing.Callable[[int], float]


@typing.overload
def retry( # type: ignore
    func: typing.Optional[Function[_P, _R]] = None,
    *,
    exc_type: typing.Optional[
        typing.Union[
            typing.Tuple[typing.Type[BaseException], ...], typing.Type[BaseException]
        ]
    ] = None,
    count: int = 1,
    backoff: typing.Optional[typing.Union[BackOffFunction, float]] = None,
) -> typing.Union[
    typing.Callable[[Function[_P, _R]], Function[_P, _R]], Function[_P, _R]
]: ...


@typing.overload
def retry( # type: ignore
    func: typing.Optional[CoroutineFunction[_P, _R]] = None,
    *,
    exc_type: typing.Optional[
        typing.Union[
            typing.Tuple[typing.Type[BaseException], ...], typing.Type[BaseException]
        ]
    ] = None,
    count: int = 1,
    backoff: typing.Optional[typing.Union[BackOffFunction, float]] = None,
) -> typing.Union[
    typing.Callable[[CoroutineFunction[_P, _R]], CoroutineFunction[_P, _R]],
    CoroutineFunction[_P, _R],
]: ...


def retry( # type: ignore
    func: typing.Optional[
        typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]]
    ] = None,
    *,
    exc_type: typing.Optional[
        typing.Union[
            typing.Tuple[typing.Type[BaseException], ...], typing.Type[BaseException]
        ]
    ] = None,
    count: int = 1,
    backoff: typing.Optional[typing.Union[BackOffFunction, float]] = None,
) -> typing.Union[
    typing.Callable[
        [typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]]],
        typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]],
    ],
    typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]],
]:
    """
    Decorator to retry a function on a specified exception.
    The function will be retried for the specified number of times,
    after which the exception will be allowed to propagate.

    :param func: The function to decorate.
    :param exc_type: The target exception type(s) to catch.
    :param count: The number of times to retry the function.
    :param backoff: The backoff function or constant value to apply between retries.
    :return: The decorated function.
    """

    def decorator(
        func: typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]],
    ) -> typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]]:
        wrapper = None
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                for i in range(count):
                    try:
                        return await func(*args, **kwargs)
                    except exc_type or Exception as exc:
                        log_exception(exc)

                        if backoff is not None:
                            if callable(backoff):
                                await asyncio.sleep(backoff(i))
                            else:
                                await asyncio.sleep(backoff)
                        continue
                return await func(*args, **kwargs)

            wrapper = async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
                for _ in range(count):
                    try:
                        return func(*args, **kwargs)  # type: ignore
                    except exc_type or Exception as exc:
                        log_exception(exc)
                        if backoff is not None:
                            if callable(backoff):
                                time.sleep(backoff(_))
                            else:
                                time.sleep(backoff)
                        continue
                return func(*args, **kwargs)  # type: ignore

            wrapper = sync_wrapper

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


class classorinstancemethod(typing.Generic[_T, _P, _R_co]):
    """
    Method decorator.

    Allows a method to be accessed from both the class and the instance.

    Example:
    ```python
    class Example:
        @classorinstancemethod
        def example(cls_or_self) -> int:
            return cls_or_self

    assert Example.example() == Example
    instance = Example()
    assert instance.example() == instance
    ```
    """

    __name__: str
    __qualname__: str
    __doc__: typing.Optional[str]

    @property
    def __func__(
        self,
    ) -> typing.Callable[
        typing.Concatenate[typing.Union[_T, typing.Type[_T]], _P], _R_co
    ]:
        return self.func

    def __init__(
        self,
        func: typing.Callable[
            typing.Concatenate[typing.Union[_T, typing.Type[_T]], _P], _R_co
        ],
        /,
    ):
        self.func = func

    @typing.overload
    def __get__(
        self, instance: _T, owner: typing.Optional[typing.Type[_T]] = None, /
    ) -> typing.Callable[_P, _R_co]: ...

    @typing.overload
    def __get__(
        self, instance: None, owner: typing.Type[_T], /
    ) -> typing.Callable[_P, _R_co]: ...

    def __get__(
        self,
        instance: typing.Optional[_T],
        owner: typing.Optional[typing.Type[_T]] = None,
        /,
    ) -> typing.Callable[_P, _R_co]:
        if instance is None:  # Accessed from the class
            return classmethod(self.func).__get__(None, owner)  # type: ignore
        # Accessed from the instance
        return functools.partial(self.func, instance)
