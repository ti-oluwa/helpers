from typing import Callable, Optional, TypeVar, Union, overload

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec
import time
from contextlib import ContextDecorator
import cProfile
import pstats
import io

_P = ParamSpec("_P")
_R = TypeVar("R")


class _timeit(ContextDecorator):
    """Context manager/decorator to measure the time taken to execute a function or block of code."""

    def __init__(
        self,
        identifier: str = None,
        output: Callable = None,
        use_perf_counter: bool = True,
    ) -> None:
        """
        Create a new instance of the _timeit class.

        :param identifier: A unique identifier for the function or block.
        :param output: The output/writer function to use. This defaults to `print`.
        :param use_perf_counter: If True, use time.perf_counter() for higher precision timing.
        """
        self.identifier = identifier
        self.output = output or print
        self.timer_func = time.perf_counter if use_perf_counter else time.monotonic
        self.start = None
        self.end = None

    def __enter__(self) -> None:
        self.start = self.timer_func()

    def __exit__(self, *exc) -> None:
        self.end = self.timer_func()
        time_taken = self.end - self.start
        if self.identifier:
            self.output(f"'{self.identifier}' executed in {time_taken} seconds.\n")
        else:
            self.output(f"Execution took {time_taken} seconds.\n")

    def __call__(self, func: Callable[_P, _R]) -> Callable[_P, _R]:
        self.identifier = self.identifier or func.__name__
        return super().__call__(func)


@overload
def timeit(
    identifier: str,
    func: Optional[Callable[_P, _R]] = None,
    *,
    output: Optional[Callable] = None,
    use_perf_counter: bool = True,
) -> Union[_timeit, Callable[_P, _R]]: ...


@overload
def timeit(
    func: Optional[Callable[_P, _R]] = None,
    *,
    identifier: Optional[str] = None,
    output: Optional[Callable] = None,
    use_perf_counter: bool = True,
) -> Union[_timeit, Callable[_P, _R]]: ...


def timeit(
    func: Optional[Callable[_P, _R]] = None,
    identifier: Optional[str] = None,
    output: Optional[Callable] = None,
    use_perf_counter: bool = True,
) -> Union[_timeit, Callable[_P, _R]]:
    """
    Measure the time taken to execute a function or block of code.

    :param func: The function to be measured.
    :param identifier: A unique identifier for the function or block.
    :param output: The output/writer function to use. This defaults to `print`.
    :param use_perf_counter: If True, use time.perf_counter() for higher precision timing.

    Example:
    ```python
    # Usage as a context manager
    with timeit("Block identifier"):
        # Code block

    # Usage as a decorator
    @timeit
    def my_function():
        # Function code
    ```
    """
    if isinstance(func, str):
        context_decorator = _timeit(
            identifier=func,
            output=output,
            use_perf_counter=use_perf_counter,
        )
        if identifier:
            return context_decorator(identifier)
        return context_decorator

    context_decorator = _timeit(
        identifier=identifier,
        output=output,
        use_perf_counter=use_perf_counter,
    )
    if func:
        return context_decorator(func)
    return context_decorator


class _Profiler(ContextDecorator):
    """
    Context manager/decorator to profile a function or block of code using cProfile.
    """

    def __init__(
        self,
        identifier: Optional[str] = None,
        output: Optional[Callable] = None,
        timeunit: Optional[float] = None,
        builtins: bool = False,
    ) -> None:
        """
        Initialize the profiler.

        :param identifier: A unique identifier for the function or block.
        :param output: The output/writer function to use. This defaults to `print`.
        :param timeunit: Multiplier for converting profiler timer measurements to seconds.
                          For example, 1e-6 for microseconds.
        """
        self.identifier = identifier
        self.output = output or print
        self.profiler = (
            cProfile.Profile(timeunit=timeunit, builtins=builtins)
            if timeunit
            else cProfile.Profile(builtins=builtins)
        )

    def __enter__(self) -> None:
        self.profiler.enable()

    def __exit__(self, *exc) -> None:
        self.profiler.disable()
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream).sort_stats(
            pstats.SortKey.TIME
        )
        stats.print_stats()
        info = stream.getvalue()
        if self.identifier:
            self.output(f"=== {self.identifier} Profiling Stats ===\n{info.lstrip()}")
        else:
            self.output(f"=== Profiling Stats ===\n{info.lstrip()}")

    def __call__(self, func: Callable[_P, _R]) -> Callable[_P, _R]:
        self.identifier = self.identifier or func.__name__
        return super().__call__(func)


@overload
def profileit(
    identifier: str,
    func: Optional[Callable[_P, _R]] = None,
    *,
    output: Optional[Callable] = None,
    timeunit: Optional[float] = None,
    builtins: bool = False,
) -> Union[_Profiler, Callable[_P, _R]]: ...


@overload
def profileit(
    func: Optional[Callable[_P, _R]] = None,
    *,
    identifier: Optional[str] = None,
    output: Optional[Callable] = None,
    timeunit: Optional[float] = None,
    builtins: bool = False,
) -> Union[_Profiler, Callable[_P, _R]]: ...


def profileit(
    func: Optional[Callable[_P, _R]] = None,
    identifier: Optional[str] = None,
    output: Optional[Callable] = None,
    timeunit: Optional[float] = None,
    builtins: bool = False,
) -> Union[_Profiler, Callable[_P, _R]]:
    """
    Profile a function or block of code. Can be used as a decorator or context manager,
    similar to 'timeit'.

    :param func: The function to be profiled.
    :param identifier: A unique identifier for the function or block.
    :param output: The output/writer function to use. This defaults to `print`.
    :param timeunit: Multiplier for converting profiler timer measurements to seconds.

    Example:
    ```python
    # Usage as a decorator
    @profileit
    def my_func():
        ...

    # Usage as a context manager
    with profileit("search-operation"):
        ...
    ```
    """
    if isinstance(func, str):
        return _Profiler(
            identifier=func,
            output=output,
            timeunit=timeunit,
            builtins=builtins,
        )

    profiler = _Profiler(
        identifier=identifier,
        output=output,
        timeunit=timeunit,
        builtins=builtins,
    )
    if func:
        return profiler(func)
    return profiler
