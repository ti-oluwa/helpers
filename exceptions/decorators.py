from typing import Callable, Optional
import functools

from ..logging import log_exception


def retry(
    func: Optional[Callable] = None,
    *,
    exception_class: type[BaseException] = BaseException,
    count: int = 1,
):
    """
    Decorator to retry a function on a specified exception.
    The function will be retried for the specified number of times,
    after which the exception will be allowed to propagate.

    :param func: The function to decorate.
    :param exception_class: The exception to catch.
    :param count: The number of times to retry the function.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for _ in range(count):
                try:
                    return func(*args, **kwargs)
                except exception_class as exc:
                    log_exception(exc)
                    continue
            return func(*args, **kwargs)

        return wrapper

    if func is None:
        return decorator
    return decorator(func)
