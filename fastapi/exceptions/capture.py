"""
Exception Capturing API.

Use `capture.exception_captured_handler` to enable exception capture globally in FastAPI.

Use the `capture.enable` decorator to enable for specific endpoints/routes only.
"""

import copy
import inspect
import pydantic
import typing
from typing_extensions import Self

from fastapi.exceptions import RequestValidationError, ValidationException
from starlette.requests import HTTPConnection
from starlette.responses import Response
from helpers.fastapi.utils.sync import sync_to_async
from helpers.generics.exceptions.capture import ExceptionCaptor as BaseExceptionCaptor
from helpers.generics.utils.decorators import classorinstancemethod


class ExceptionCaptor(BaseExceptionCaptor[BaseException, Response]):
    DEFAULT_RESPONSE_TYPE = Response
    EXCEPTION_CODES = {
        pydantic.ValidationError: 422,
        RequestValidationError: 422,
        ValidationException: 422,
    }
    CONTENT_TYPE_KWARG = "media_type"
    DEFAULT_CONTENT_TYPE = "application/json"
    STATUS_CODE_KWARG = "status_code"

    # Override the way sync functions are run
    # to use the FastAPI friendly `sync_to_async` utility
    # instead of that of asgiref
    @classmethod
    async def run_async(cls, func, *args, **kwargs):
        return await sync_to_async(func)(*args, **kwargs)

    async def as_dependency(
        cls_or_self: typing.Union[Self, typing.Type[Self]],
    ) -> typing.AsyncGenerator[Self, None]:
        """
        Dependency factory for FastAPI.

        Allows usage as a dependency in FastAPI endpoints.

        Using this method to inject an `ExceptionCaptor` instance as a dependency,
        notice that you do not need to use context manager syntax to capture exceptions
        within the endpoint, as this is done automatically by FastAPI.

        Usage Examples:
        ```python
        from fastapi import Depends
        from helpers.fastapi.exceptions.capture import ExceptionCaptor as capture

        @app.get("/test")
        async def test(captor: Depends(capture.as_dependency)):
            raise ValueError("This is a test error")
        ```

        Or use an instance directly;

        ```python
        captor = capture((ValueError, TypeError), callback=custom_callback_0)
        captor.add_callback(custom_callback_1)

        @app.get("/test")
        async def test(captor: capture = Depends(captor.as_dependency)):
            captor.add_callback(custom_callback_2, priority=10)
            raise ValueError("This is a test error")
        ```
        """
        if inspect.isclass(cls_or_self):
            captor = cls_or_self()
        else:
            captor = copy.copy(cls_or_self)

        async with captor:
            yield captor

    as_dependency = classorinstancemethod(as_dependency)


# Export Aliases
capture = ExceptionCaptor
enable = ExceptionCaptor.enable


async def exception_captured_handler(
    connection: HTTPConnection, exc: ExceptionCaptor.ExceptionCaptured
):
    """
    Handles exceptions captured by `ExceptionCaptor`.

    Returns the prepared response for the captured exception.
    """
    return exc.response


__all__ = [
    "ExceptionCaptor",
    "capture",
    "enable",
    "exception_captured_handler",
]
