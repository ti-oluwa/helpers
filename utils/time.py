from typing import Any, Callable, Optional
import time
import sys
from contextlib import ContextDecorator


class _timeit(ContextDecorator):
    """Context manager/decorator to measure the time taken to execute a function or block of code."""

    def __init__(self, identifier: str = None, output: Callable = None) -> None:
        """
        Create a new instance of the _timeit class.

        :param identifier: A unique identifier for the function or block.
        :param output: The output/writer function to use. This defaults to `sys.stdout.write`.
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

    def __call__(self, func):
        self.identifier = self.identifier or func.__name__
        return super().__call__(func)


def timeit(
    func: Optional[Callable[..., Any]] = None,
    *,
    identifier: str = None,
    output: Callable = None,
) -> Callable[..., Any]:
    """
    Measure the time taken to execute a function or block of code.

    :param func: The function to be measured.
    :param identifier: A unique identifier for the function or block.
    :param output: The output/writer function to use. This defaults to sys.stdout.write.

    Example:
    ```python
    with timeit(identifier="Unique name"):
        # Code block

    @timeit
    def my_function():
        # Function code
    ```
    """
    if func is None:
        return _timeit(identifier, output)
    return _timeit(identifier, output)(func)
