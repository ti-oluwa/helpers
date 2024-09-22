"""
Django Exception Capturing API.

Use `capture.drf_exception_handler` to enable exception capture globally when using DRF.

Use the `capture.enable` decorator to enable for specifc views only, especially, non-drf views.
"""

from __future__ import annotations
import json
from typing import (
    Any,
    Callable,
    Dict,
    NoReturn,
    Tuple,
    TypeVar,
    Optional,
    Union,
    TypedDict,
    Type,
)
from typing_extensions import Unpack
from django.http import HttpResponse, Http404
from django.core.exceptions import PermissionDenied, BadRequest, ValidationError
import functools
from django.utils.itercompat import is_iterable
import asyncio

from ..logging import log_exception
from ..views.contextmanagers import ViewContextDecorator
from ..utils import is_exception_class
from ..views import is_view_class, FBV, CBV

# Why this you say? I'm just too lazy to catch exceptions myself

ErrorType = TypeVar("ErrorType", bound=BaseException)
ResponseType = TypeVar("ResponseType", bound=HttpResponse)


class ExceptionCaptured(Exception):
    """Raised when an exception is captured by the `Capture` context manager."""

    def __init__(
        self, captive: ErrorType, captor: Capture, response: ResponseType
    ) -> None:
        """
        Raised when an exception is captured by the `Capture` context manager.

        :param captive: The exception that was captured
        :param captor: The `Capture` context manager that captured the exception
        :param response: The response to be returned
        """
        self.captive = captive
        self.response = response
        self.captor = captor
        super().__init__(captive)


special_exceptions = {
    (ValidationError, 422),
    (Http404, 404),
    (PermissionDenied, 403),
    (BadRequest, 400),
}
"""
A set of special exceptions with status codes.

These exceptions are treated differently on capture
"""


def register_exception(exc_class: type[ErrorType], status_code: int) -> None:
    """
    Register an exception class with a status code to the set of special exceptions.

    :param exc_class: The exception class to register
    :param status_code: The status code to associate with the exception class
    """
    global special_exceptions
    special_exceptions.add((exc_class, status_code))


def unregister_exception(exc_class: type[ErrorType]) -> None:
    """
    Unregister an exception class from the special exceptions.

    :param exc_class: The exception class to unregister
    """
    global special_exceptions
    for exc, _ in special_exceptions:
        if exc == exc_class:
            special_exceptions.remove((exc, _))
            break
    return


def special_exception_types() -> Tuple[type[ErrorType], ...]:
    """Get the exception types registered as special exceptions."""
    return tuple(exc for exc, _ in special_exceptions)


class Capture(ViewContextDecorator):
    """
    Captures exception and gives a response.

    Ensure you have enabled the capture API for the view using the `enable` decorator.
    Or globally using the exception handler.
    """

    def __init__(
        self,
        target: Optional[Union[Type[ErrorType], Tuple[Type[ErrorType]]]] = None,
        content: Optional[Any] = None,
        code: int = 500,
        response_type: Optional[ResponseType] = None,
        response_kwargs: Optional[Dict[str, Any]] = None,
        prioritize_content: bool = False,
        callback: Optional[Callable[..., None]] = None,
        log_errors: bool = True,
    ) -> None:
        """
        Captures exception and gives a response.

        :param target: Type of exception(s) to capture. Defaults to `BaseException`
        :param content: The content or message to be returned in the response. If not provided,
            exception detail will be used. This can also be a callable that will take the exception captured,
            process the result and return appropriate content to be returned in the response
        :param code: The status code of the response. Defaults to 500
        :param response_type: Type of response to return. Defaults to `HttpResponse`
        :param response_kwargs: Keyword arguments to pass on to the response constructor
        :param prioritize_content: Whether to prioritize the content over the exception detail.
            By default, the exception detail takes precedence over the content.
        :param callback: A callback to be called on exception capture. Should take the exception as an argument
        :param log_errors: Whether to log server errors, that is, status code 500. Defaults to True
        """
        target = target or (BaseException,)
        if not is_iterable(target):
            target = (target,)
        for exc_class in target:
            if not is_exception_class(exc_class):
                raise ValueError("target should only hold exception classes")

        self.target = tuple(target)
        self.content = content
        self.prioritize_content = prioritize_content
        self.code = code
        self.response_type = response_type or HttpResponse
        response_kwargs = response_kwargs or {}
        if self.response_type == HttpResponse:
            response_kwargs.setdefault("content_type", "application/json")
        self.response_kwargs = response_kwargs
        self.callbacks = ()
        if callback:
            self.add_callback(callback)
        self.log_errors = log_errors

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type and self.verify_target(exc_type):
            self.execute_callbacks(exc_value)
            return self.raise_exception_captured(exc_value)
        # Raise the exception if it is not of the given type
        return False

    def verify_target(self, exc_type: type[ErrorType]) -> bool:
        """Verify if the exception type is of the target type(s)."""
        return issubclass(exc_type, self.target) and not issubclass(
            exc_type, ExceptionCaptured
        )

    def get_exc_detail(self, exc: ErrorType) -> Any | str:
        """Get the detail of the exception."""
        return getattr(exc, "detail", str(exc))

    def get_response_content(self, exc: ErrorType) -> str | Any:
        """Get the content to be returned in the response."""
        content = self.content
        exc_detail = self.get_exc_detail(exc)

        if self.response_kwargs.get("content_type") == "application/json":
            if content:
                if callable(content):
                    content = content(exc)
                content = json.loads(json.dumps(content))

            if not self.prioritize_content:
                if isinstance(exc_detail, dict):
                    if isinstance(content, dict):
                        content.update(exc_detail)
                    else:
                        content = exc_detail
                elif isinstance(exc_detail, list):
                    if isinstance(content, dict):
                        content.update({"detail": exc_detail})
                    else:
                        content = {"detail": exc_detail}
                else:
                    if isinstance(exc, special_exception_types()):
                        content = {"detail": exc_detail}
                    else:
                        content = {"detail": content or exc_detail}

            if not content:
                content = {"detail": exc_detail}
            content = json.dumps(content)
        else:
            if self.prioritize_content:
                content = content or exc_detail
            else:
                if isinstance(exc, special_exception_types()):
                    content = exc_detail
                else:
                    content = content or exc_detail
        return content

    def get_response_code(self, exc: ErrorType) -> int:
        """Get the status code to be returned in the response."""
        response_code = self.code
        # If the status code was specified explicitly
        # for some special exceptions, override it
        if type(exc) not in self.target:
            for exc_class, code in special_exceptions:
                if isinstance(exc, exc_class):
                    response_code = code
                    break
            else:
                if hasattr(exc, "status_code"):
                    response_code = exc.status_code
        return response_code

    def get_response_kwargs(self, exc: ErrorType) -> Dict[str, Any]:
        """Get the content to be returned in the response."""
        kwargs = self.response_kwargs.copy()
        try:
            headers: Dict[str, Any] = kwargs["headers"]
        except KeyError:
            pass
        else:
            if "Content-Type" in headers and "content_type" in kwargs:
                # Headers "Content-Type" takes precedence over content_type
                kwargs.pop("content_type", None)

        status_code = self.get_response_code(exc)
        return {**kwargs, "status": status_code}

    def construct_response(self, exc: ErrorType) -> ResponseType:
        """Construct the response to be returned."""
        content = self.get_response_content(exc)
        kwargs = self.get_response_kwargs(exc)
        return self.response_type(content, **kwargs)

    def raise_exception_captured(self, exc: ErrorType) -> NoReturn:
        """Raise the exception captured."""
        response = self.construct_response(exc)
        if response.status_code == 500 and self.log_errors:
            log_exception(exc)
        raise ExceptionCaptured(exc, self, response)

    def add_callback(self, callback: Callable[..., None], **kwargs) -> None:
        """
        Add callbacks to be called on exception capture.

        Provides an opportunity to add clean-up logic
        :param callback: The callback to be called
        :param kwargs: The keyword arguments to pass to the callback
        """
        if kwargs:
            callback = functools.partial(callback, **kwargs)
        self.callbacks = (callback, *self.callbacks)
        return None

    def execute_callbacks(self, exc: ErrorType) -> None:
        """Execute the callbacks."""
        for callback in self.callbacks:
            try:
                callback(exc)
            except BaseException as e:
                if self.log_errors:
                    log_exception(e)
                pass
        return

    def _decorate_view_function(self, view: FBV) -> FBV:
        # If the view has been enabled for capture,
        # that means it has already been decorated
        # by the `enable` decorator, and is wrapped.
        # Hence, we decorate the wrapped view instead
        if getattr(view, "capture_enabled", False):
            view.wrapped_view = self(view.wrapped_view)
            return view
        return super()._decorate_view_function(view)


class CaptureKwargs(TypedDict):
    """Mapping of keyword arguments for the `Capture` context manager."""
    
    content: Optional[Any]
    """The content or message to be returned in the response. If not provided,
        exception detail will be used. This can also be a callable that will take the exception captured,
        process the result and return appropriate content to be returned in the response"""
    code: int
    """The status code of the response. Defaults to 500"""
    response_type: Optional[ResponseType]
    """Type of response to return. Defaults to `HttpResponse`"""
    response_kwargs: Optional[Dict[str, Any]]
    """Keyword arguments to pass on to the response constructor"""
    prioritize_content: bool
    """Whether to prioritize the content over the exception detail.
        By default, the exception detail takes precedence over the content."""
    callback: Optional[Callable[..., None]]
    """A callback to be called on exception capture. Should take the exception as an argument"""
    log_errors: bool
    """Whether to log server errors, that is, status code 500. Defaults to True"""


def capture(
    target: Optional[Union[Type[ErrorType], Tuple[Type[ErrorType]]]] = None,
    **kwargs: Unpack[CaptureKwargs],
) -> Capture:
    """
    Captures exception and gives a response.

    :param target: The type of exception to capture. Defaults to `BaseException`.
    Can be a single exception class or a tuple of exception classes.
    :param content: The content or message to be returned in the response. If not provided,
        exception detail will be used. This can also be a callable that will take the exception captured,
        process the result and return appropriate content to be returned in the response
    :param code: The status code of the response. Defaults to 500.
    :param kwargs: Additional keyword arguments to pass to the `Capture` context manager.

    Example:
    ```python
    from helpers.exceptions import capture

    def view(request, *args, **kwargs):
        ...
        with capture.capture(ValueError, {"message": "Invalid value"}, code=400) as captor:
            raise ValueError("Invalid value")
        ...
    ```

    Or;
    ```python
    @capture.capture(ValueError, {"message": "Invalid value"}, code=400)
    def view(request, *args, **kwargs):
        raise ValueError("Invalid value")
    ```
    """
    return Capture(target, **kwargs)


def enable(view: Union[FBV, CBV]):
    """
    Enables the exception Capture API on the decorated view.

    This is intended for use with non-DRF (regular Django) views. If you are using DRF,
    use the `capture.drf_exception_handler` instead.

    Example:
    ```python
    @capture.enable
    def view(request, *args, **kwargs):
        ...
        with capture.capture(ValueError, {"message": "Invalid value"}, code=400) as captor:
            raise ValueError("Invalid value")
        ...
    ```

    Or;
    ```python
    @capture.enable
    class MyView(View):
        ...
    """
    if getattr(view, "capture_enabled", False):
        return view

    if is_view_class(view):
        for method in view.http_method_names:
            method = method.lower()
            view_method = getattr(view, method, None)
            if not view_method:
                continue
            setattr(view, method, enable(view_method))
        return view

    if asyncio.iscoroutinefunction(view):

        @functools.wraps(view)
        async def wrapper(*args, **kwargs) -> ResponseType:
            try:
                return await wrapper.wrapped_view(*args, **kwargs)
            except ExceptionCaptured as exc:
                return exc.response
    else:

        @functools.wraps(view)
        def wrapper(*args, **kwargs) -> ResponseType:
            try:
                return wrapper.wrapped_view(*args, **kwargs)
            except ExceptionCaptured as exc:
                return exc.response

    wrapper.capture_enabled = True
    wrapper.wrapped_view = view
    return wrapper


def drf_exception_handler(exc, context):
    """
    Exception handler for Django Rest Framework.

    Processes `ExceptionCaptured` exceptions and leaves the rest
    to `rest_framework.views.drf_exception_handler`

    Example:
    ```python
    REST_FRAMEWORK = {
        "EXCEPTION_HANDLER": "helpers.exceptions.capture.drf_exception_handler"
    }
    ```
    """
    from rest_framework import views, exceptions

    if isinstance(exc, ExceptionCaptured):
        response = exc.response
        captured_exception = exc.captive

        if isinstance(captured_exception, exceptions.APIException):
            if getattr(exc, "auth_header", None):
                response.headers["WWW-Authenticate"] = exc.auth_header
            if getattr(exc, "wait", None):
                response.headers["Retry-After"] = "%d" % exc.wait
            views.set_rollback()
        return response

    return views.exception_handler(exc, context)
