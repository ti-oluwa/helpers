from typing import Callable, Optional, TypeVar, Union, overload
try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec
import time
import sys
from contextlib import ContextDecorator


_P = ParamSpec("_P")
_R = TypeVar("R")
_C = TypeVar("_C", bound=Callable[_P, _R])


class _timeit(ContextDecorator):
    """Context manager/decorator to measure the time taken to execute a function or block of code."""

    def __init__(self, identifier: str = None, output: Callable = None) -> None:
        """
        Create a new instance of the _timeit class.

        :param identifier: A unique identifier for the function or block.
        :param output: The output/writer function to use. This defaults to sys.stdout.write.
        """
        self.identifier = identifier
        self.start = None
        self.end = None
        self.output = output or sys.stdout.write

    def __enter__(self) -> None:
        self.start = time.monotonic()

    def __exit__(self, *exc) -> None:
        self.end = time.monotonic()
        time_taken = self.end - self.start
        if self.identifier:
            self.output(f"'{self.identifier}' executed in {time_taken} seconds.\n")
        else:
            self.output(f"Execution took {time_taken} seconds.\n")

    def __call__(self, func: _C) -> _C:
        self.identifier = self.identifier or func.__name__
        return super().__call__(func)


@overload
def timeit(
    identifier: str,
    func: Optional[_C] = None,
    *,
    output: Optional[Callable] = None,
) -> Union[_timeit, _C]: ...


@overload
def timeit(
    func: Optional[_C] = None,
    *,
    identifier: Optional[str] = None,
    output: Optional[Callable] = None,
) -> Union[_timeit, _C]: ...


def timeit(
    func: Optional[_C] = None,
    identifier: Optional[str] = None,
    output: Optional[Callable] = None,
) -> Union[_timeit, _C]:
    """
    Measure the time taken to execute a function or block of code.

    :param func: The function to be measured.
    :param identifier: A unique identifier for the function or block.
    :param output: The output/writer function to use. This defaults to sys.stdout.write.

    Example:
    ```python
    with timeit("Block identifier"):
        # Code block

    @timeit
    def my_function():
        # Function code
    ```
    """
    if isinstance(func, str):
        context_decorator = _timeit(identifier=func, output=output)
        if identifier:
            return context_decorator(identifier)
        return context_decorator

    context_decorator = _timeit(identifier=identifier, output=output)
    if func:
        return context_decorator(func)
    return context_decorator
