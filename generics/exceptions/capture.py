"""
Exception Capturing API.

Use an appropriate `ExceptionCaptured` exception handler` to enable exception capture globally.
Or use the `capture.enable` decorator to enable for specific controllers only.
"""

import copy
import logging
import json
import typing
import functools
from asyncio import iscoroutinefunction
import inspect
from typing_extensions import ParamSpec, Self
from dataclasses import dataclass, field

from helpers.dependencies import depends_on
from helpers.logging import log_exception
from helpers.generics.utils.misc import is_iterable, is_exception_class, is_mapping
from helpers.types import Function, CoroutineFunction

# Why this you say? I'm just too lazy to catch exceptions myself. I know. Its overkill.

P = ParamSpec("P")
R = typing.TypeVar("R")

JSON_CONTENT_TYPE = "application/json"
TEXT_PREFIX = "text/"
JSON_SUFFIX = "+json"


@functools.lru_cache(maxsize=32)
def is_text_content_type(content_type: str) -> bool:
    """Return True if the content type is a text content type. Otherwise, False."""
    return (
        content_type.startswith(TEXT_PREFIX)
        or content_type == JSON_CONTENT_TYPE
        or content_type.endswith(JSON_SUFFIX)
    )


@functools.lru_cache(maxsize=32)
def is_json_content_type(content_type: str) -> bool:
    """Return True if the content type is a JSON content type. Otherwise, False."""
    return content_type == JSON_CONTENT_TYPE


class Response(typing.Protocol):
    """
    Protocol defining a generic interface for a HTTP response.
    """

    status_code: int
    headers: typing.Any
    body: typing.Any


ResponseType = typing.TypeVar("ResponseType", bound=Response, covariant=True)
ControllerFunc = typing.Union[
    Function[P, ResponseType], CoroutineFunction[P, ResponseType]
]
ExceptionType = typing.TypeVar("ExceptionType", bound=BaseException, contravariant=True)


class DjangoControllerClass(typing.Generic[ResponseType], typing.Protocol):
    http_method_names: list[str]

    @classmethod
    def as_view(
        cls, **initkwargs: typing.Any
    ) -> typing.Callable[..., ResponseType]: ...
    def setup(self, *args: typing.Any, **kwargs: typing.Any) -> None: ...
    def dispatch(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseType: ...
    def http_method_not_allowed(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> ResponseType: ...
    def options(self, *args: typing.Any, **kwargs: typing.Any) -> ResponseType: ...


class ControllerContextDecorator(typing.Generic[ExceptionType, ResponseType]):
    """
    Context decorator interface.

    Can be used as a regular sync/async context manager,
    and as a decorator on request handlers/controllers.

    Works with both sync and async controllers.
    """

    @typing.overload
    def __call__(
        self, controller: typing.Type[DjangoControllerClass[ResponseType]]
    ) -> typing.Type[DjangoControllerClass[ResponseType]]: ...

    @typing.overload
    def __call__(
        self, controller: ControllerFunc[P, ResponseType]
    ) -> ControllerFunc[P, ResponseType]: ...

    @typing.overload
    def __call__(self) -> Self: ...

    def __call__(
        self,
        controller: typing.Optional[
            typing.Union[
                typing.Type[DjangoControllerClass[ResponseType]],
                ControllerFunc[P, ResponseType],
            ]
        ] = None,
    ) -> typing.Union[
        typing.Type[DjangoControllerClass[ResponseType]],
        ControllerFunc[P, ResponseType],
        Self,
    ]:
        """
        Allows usage as a decorator.

        If a controller is provided, it decorates the controller.
        Else, returns the instance for reuse.

        :param controller: The controller to decorate
        :return: The decorated controller or the instance
        """
        if controller is None:
            return self

        if inspect.isclass(controller):
            return self.decorate_controller_cls(controller)
        return self.decorate_controller_func(controller)

    def decorate_controller_cls(
        self, controller_cls: typing.Type[DjangoControllerClass[ResponseType]]
    ) -> typing.Type[DjangoControllerClass[ResponseType]]:
        """Decorate class-based controller."""
        if not hasattr(controller_cls, "http_method_names"):
            return controller_cls

        for method_name in controller_cls.http_method_names:
            method_name = method_name.lower()
            handler: typing.Optional[ControllerFunc] = getattr(
                controller_cls, method_name, None
            )
            if not handler or not callable(handler):
                continue
            setattr(controller_cls, method_name, self.decorate_controller_func(handler))
        return controller_cls

    def decorate_controller_func(
        self, controller_func: ControllerFunc[P, ResponseType]
    ) -> ControllerFunc[P, ResponseType]:
        """Decorate function-based controller."""
        wrapper = None
        if iscoroutinefunction(controller_func):

            @functools.wraps(controller_func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> ResponseType:
                async with self:
                    return await controller_func(*args, **kwargs)

            wrapper = async_wrapper
        else:

            @functools.wraps(controller_func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> ResponseType:
                with self:
                    return controller_func(*args, **kwargs)  # type: ignore

            wrapper = sync_wrapper

        return wrapper

    @classmethod
    @depends_on({"asgiref": "asgiref"})
    async def run_async(
        cls, sync_func: Function[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        """
        Run a synchronous function asynchronously.

        :param sync_func: The synchronous function to run asynchronously
        :param args: The positional arguments to pass to the function
        :param kwargs: The keyword arguments to pass to the function
        """
        from asgiref.sync import sync_to_async  # type: ignore[import]

        return await sync_to_async(sync_func, thread_sensitive=True)(*args, **kwargs)

    @classmethod
    @depends_on({"asgiref": "asgiref"})
    def run_sync(
        cls, async_func: CoroutineFunction[P, R], *args: P.args, **kwargs: P.kwargs
    ) -> R:
        """
        Run an asynchronous function synchronously.

        :param async_func: The asynchronous function to run synchronously
        :param args: The positional arguments to pass to the function
        :param kwargs: The keyword arguments to pass to the function
        """
        from asgiref.sync import async_to_sync  # type: ignore[import]

        return async_to_sync(async_func)(*args, **kwargs)

    def __enter__(self) -> typing.Any:
        raise NotImplementedError("Subclasses must implement this method")

    def __exit__(
        self, exc_type: typing.Type[ExceptionType], exc_value: ExceptionType, traceback
    ) -> bool:
        raise NotImplementedError("Subclasses must implement this method")

    async def __aenter__(self) -> typing.Any:
        return await self.run_async(self.__enter__)

    async def __aexit__(
        self, exc_type: typing.Type[ExceptionType], exc_value: ExceptionType, traceback
    ) -> bool:
        return await self.run_async(self.__exit__, exc_type, exc_value, traceback)


P = ParamSpec("P")
R = typing.TypeVar("R", covariant=True)


class ExceptionCallback(typing.Generic[ExceptionType, P, R], typing.Protocol):
    """Protocol defining the interface for exception callbacks"""

    def __call__(
        self, exc: ExceptionType, *args: P.args, **kwargs: P.kwargs
    ) -> typing.Union[R, typing.Awaitable[R]]: ...


@functools.total_ordering
@dataclass(frozen=True)  # Ensure immutability due to ordering and caching
class PrioritizedCallback(typing.Generic[ExceptionType, P, R]):
    """Callback with priority and instance-specific order tracking"""

    callback: ExceptionCallback[ExceptionType, P, R]
    priority: typing.Union[int, float] = 0
    args: typing.Tuple[typing.Any, ...] = field(default_factory=tuple)
    kwargs: typing.Dict[str, typing.Any] = field(default_factory=dict)
    # Track order within specific captor instance
    _order: int = field(default=0)

    def __call__(
        self, exc: ExceptionType, **kwargs: typing.Any
    ) -> typing.Union[R, typing.Awaitable[R]]:
        return self.callback(exc, *self.args, **{**self.kwargs, **kwargs})

    def __lt__(self, other: typing.Any) -> bool:
        if not isinstance(other, PrioritizedCallback):
            return NotImplemented
        return (-self.priority, self._order) < (-other.priority, other._order)

    @functools.cached_property
    def is_async(self):
        """Return True if the callback is an async type. Otherwise, False."""
        return iscoroutinefunction(self.callback)


def merge_json_content_with_exception_detail(
    content: typing.Any,
    exc_detail: typing.Any,
    prioritize_content: bool,
    is_special_exception: bool,
) -> typing.Any:
    """
    Compare the content with the exception detail, merging them into a single JSON serializable content.

    :param content: The content defined to be returned in the response
    :param exc_detail: The detail of the exception
    :param prioritize_content: Whether to prioritize the defined content over the exception detail when merging them.
    :param is_special_exception: Whether the exception is to be treated with preference.
    """
    priority = content if prioritize_content else exc_detail
    non_priority = exc_detail if prioritize_content else content
    if not priority:
        return {"detail": non_priority}

    if is_mapping(priority):
        if not is_mapping(non_priority):
            non_priority = {"detail": non_priority}
        return {**non_priority, **priority}

    elif is_iterable(priority, exclude=(str, bytes)):
        if is_iterable(non_priority, exclude=(str, bytes)):
            return {"detail": list(set([*non_priority, *priority]))}
        else:
            if not is_mapping(non_priority):
                non_priority = {"detail": non_priority}
            return {**non_priority, "detail": priority}

    elif isinstance(priority, str):
        if isinstance(non_priority, str):
            return {"detail": f"{priority}. {non_priority}"}
        elif is_mapping(non_priority):
            return {**non_priority, "detail": priority}
        elif is_iterable(non_priority, exclude=(str, bytes)):
            return {"detail": list(set([*non_priority, priority]))}
        else:
            return {"detail": priority}

    # If the priority is not a string, list or dict
    # negate the main context, that is, the priority
    # becomes non-priority and vice versa, and negate
    # the `prioritize_content` flag.
    json_content = merge_json_content_with_exception_detail(
        priority,
        non_priority,
        prioritize_content=not prioritize_content,
        is_special_exception=is_special_exception,
    )
    if is_special_exception:
        json_content = {**json_content, "detail": exc_detail}
    return json_content


CAPTURE_ENABLED_ATTR = "__capture_enabled"
WRAPPED_CONTROLLER_ATTR = "wrapped_controller"


class ExceptionCaptor(ControllerContextDecorator[ExceptionType, ResponseType]):
    """
    Captures and constructs a structured error response from exceptions.

    Ensure you have enabled the capture API for the controller using the `enable` decorator.
    Or globally, using an exception handler for `ExceptionCaptured` exceptions.

    Example:
    ```python
    from helpers.generics.exceptions import capture

    @capture.enable # Enable the exception capture API for the controller only
    def controller(*args, **kwargs):
        ...
        with capture.ExceptionCaptor(
            ValueError,
            content={"message": "Unexpected value"},
            code=422
        ) as captor:
            captor.add_callback(lambda exc: print(exc))
            raise ValueError(...)
        ...
    ```

    Or;
    ```python

    @capture.enable # or use the `exception_captured_handler` globally
    @capture.capture(
        (ValueError, KeyError),
        content="Invalid value",
        prioritize_content=True,
        code=400
    )
    async def controller(*args, **kwargs):
        key = kwargs["key"]
        if condition:
            raise ValueError(...)
    ```
    """

    EXCEPTION_CODES: typing.Mapping[typing.Type[BaseException], int] = {}
    """
    A mapping of special exceptions to the preferred status codes to be used for them
    when constructing response.
    """
    DEFAULT_RESPONSE_TYPE: typing.Optional[typing.Type[ResponseType]] = None
    """
    The default response type/class to use to construct the response.

    Make sure to set this to an appropriate response class before instantiation.
    Else, provide the `response_type` argument on instantiation.
    """
    CONTENT_TYPE_KWARG: str = "content_type"
    """
    The name of the keyword argument that represents the content type in the response constructor.
    """
    DEFAULT_CONTENT_TYPE: str = "application/json"
    """
    The default content type to use when constructing the response.

    Override this by providing the `response_kwargs["content_type"]` argument on instantiation.
    """
    STATUS_CODE_KWARG: str = "status_code"
    """
    The name of the keyword argument that represents the status code in the response constructor.
    """
    DEFAULT_STATUS_CODE: int = 500
    """
    The default status code to use when constructing the response.

    Override this by providing the `code` argument on instantiation.
    """
    DEFAULT_RESPONSE_FORMATTER: typing.Optional[
        typing.Union[
            Function[[ResponseType], ResponseType],
            CoroutineFunction[[ResponseType], ResponseType],
        ]
    ] = None
    """The default response formatter to be used by instances."""

    @typing.final
    class ExceptionCaptured(Exception, typing.Generic[ExceptionType, ResponseType]):  # type: ignore
        """Raised when an exception is captured by an ExceptionCaptor instance."""

        __outer__ = None

        def __init__(
            self,
            captive: ExceptionType,
            captor: "ExceptionCaptor[ExceptionType, ResponseType]",
            response: ResponseType,
        ) -> None:
            super().__init__(captive)
            self.captive = captive
            self.response = response
            self.captor = captor

    def __init__(
        self,
        target: typing.Optional[
            typing.Union[
                typing.Type[ExceptionType],
                typing.Tuple[typing.Type[ExceptionType], ...],
            ]
        ] = None,
        content: typing.Optional[typing.Any] = None,
        *,
        code: typing.Optional[int] = None,
        response_type: typing.Optional[ResponseType] = None,
        response_kwargs: typing.Optional[typing.MutableMapping[str, typing.Any]] = None,
        response_formatter: typing.Optional[
            typing.Union[
                Function[[ResponseType], ResponseType],
                CoroutineFunction[[ResponseType], ResponseType],
            ]
        ] = None,
        prioritize_content: bool = False,
        callback: typing.Optional[
            typing.Union[
                ExceptionCallback[ExceptionType, P, R],
                PrioritizedCallback[ExceptionType, P, R],
            ]
        ] = None,
        log_errors: bool = True,
        logger: typing.Optional[typing.Union[str, logging.Logger]] = None,
    ) -> None:
        """
        Initialize the `ExceptionCaptor` instance.

        :param target: Type of exception(s) to capture. Defaults to `BaseException`
        :param content: The content or message to be returned in the response. If not provided,
            exception detail will be used. This can also be a callable that will take the exception captured,
            process the result and return appropriate content to be returned in the response
        :param code: The status code of the response. Defaults to 500
        :param response_type: Type of response to return. Defaults to `HttpResponse`
        :param response_kwargs: Keyword arguments to pass on to the response constructor.
        :param response_formatter: Callable to be used to perform additional formatting on the prepared response.
        :param prioritize_content: Whether to prioritize the content over the exception detail.
            By default, the exception detail takes precedence over the content.
        :param callback: A callback to be called on exception capture. Should take the exception as an argument.
            By default, callback added on instantiation will have the highest priority, no matter the order of addition.
            However, the callback this can be circumvented by providing an already created `PrioritizedCallback` instance.
        :param log_errors: Whether to log critical exceptions (like server errors) or errors during captured
            exception processing. Defaults to True.
        :param logger: The logger to use for logging exceptions. Defaults to the module logger.
        """
        target_exceptions = target or (BaseException,)
        if not is_iterable(target_exceptions):
            target_exceptions = (target_exceptions,)

        for exc_class in target_exceptions:
            if not is_exception_class(exc_class):
                raise ValueError("target should only hold exception classes")

        self.target = tuple(target_exceptions)
        self.content = content
        self.prioritize_content = prioritize_content
        self.code = code or self.DEFAULT_STATUS_CODE

        self.response_type = response_type or self.DEFAULT_RESPONSE_TYPE
        if self.response_type is None:
            raise ValueError(
                "`response_type` must be provided if DEFAULT_RESPONSE_TYPE is not set"
            )

        response_kwargs = response_kwargs or {}
        response_kwargs.setdefault(self.CONTENT_TYPE_KWARG, self.DEFAULT_CONTENT_TYPE)
        self.response_kwargs = response_kwargs
        self.response_formatter = response_formatter or self.DEFAULT_RESPONSE_FORMATTER
        self._callback_counter: int = 0
        self.callbacks: typing.List[PrioritizedCallback] = []
        if callback:
            # Callback added on instantiation should have the highest priority
            self.add_callback(callback, priority=float("inf"))
        self.log_errors = log_errors
        self.logger = (
            logger
            if isinstance(logger, logging.Logger)
            else logging.getLogger(logger or __name__)
        )
        self._init_args = ()
        self._init_kwargs = {}

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._init_args = args
        instance._init_kwargs = kwargs
        return instance

    def _next_callback_order(self) -> int:
        """Get next callback order for this instance"""
        self._callback_counter += 1
        return self._callback_counter

    def __repr__(self) -> str:
        return f"{type(self).__name__}(target={self.target}, code={self.code})"

    def __copy__(self) -> Self:
        args = self._init_args
        kwargs = self._init_kwargs.copy()
        kwargs.pop("callback", None)
        copy = type(self)(*args, **kwargs)

        # Using `copy.callbacks.append(callback)` will lead to shared
        # callbacks state between instances. Hence, we add callbacks
        # to the new instance in the same order as the original instance.
        # This would create new priority callbacks for the new instance.
        # in the same order as they were added to the original instance.
        for callback in sorted(self.callbacks):
            copy.add_callback(callback)
        return copy

    def verify_target(self, exc_type: typing.Type[ExceptionType]) -> bool:
        """Returns True if the exception type is of the target type(s). Otherwise, False."""
        return issubclass(exc_type, self.target) and not issubclass(
            exc_type, self.ExceptionCaptured
        )

    def get_exception_detail(self, exc: ExceptionType) -> typing.Any:
        """Returns the detail of the exception."""
        return getattr(exc, "detail", None) or str(exc)

    def prepare_response_content(self, exc: ExceptionType) -> typing.Any:
        """Prepare and returns the content of the error response."""
        content = self.content
        if callable(content):
            content = content(exc)

        exc_detail = self.get_exception_detail(exc)
        special_exceptions = tuple(self.EXCEPTION_CODES.keys())
        is_special_exception = isinstance(exc, special_exceptions)

        content_type = self.response_kwargs.get(
            self.CONTENT_TYPE_KWARG, self.DEFAULT_CONTENT_TYPE
        )
        if is_json_content_type(content_type):
            content = merge_json_content_with_exception_detail(
                content,
                exc_detail,
                prioritize_content=self.prioritize_content,
                is_special_exception=is_special_exception,
            )
            content = json.dumps(content)
        else:
            if self.prioritize_content:
                content = content or exc_detail
            else:
                if is_special_exception:
                    content = exc_detail
                else:
                    content = exc_detail or content

            if is_text_content_type(content_type):
                content = str(content)
        return content

    def get_exception_status_code(self, exc: ExceptionType) -> int:
        """Returns the appropriate response status code for the exception."""
        # If the exception was explicitly defined in `target`,
        # return the status code defined in the instance
        if type(exc) in self.target:
            return self.code

        # If a status code was defined in `EXCEPTION_CODES`
        # for the exception type, return the status code
        for exc_class, code in self.EXCEPTION_CODES.items():
            if isinstance(exc, exc_class):
                return code
        else:
            code = self.code
            if hasattr(exc, "status_code"):
                code = exc.status_code  # type: ignore
            elif hasattr(exc, "code"):
                code = exc.code  # type: ignore
        return int(code)

    def prepare_response_kwargs(
        self, exc: ExceptionType
    ) -> typing.Dict[str, typing.Any]:
        """Prepares and returns the keyword arguments for the response constructor."""
        kwargs = copy.copy(self.response_kwargs)
        headers = kwargs.get("headers", {})
        if headers and "Content-Type" in headers:
            # Header's "Content-Type" takes precedence over `CONTENT_TYPE_KWARG`
            kwargs.pop(self.CONTENT_TYPE_KWARG, None)
            kwargs["headers"] = headers

        status_code = self.get_exception_status_code(exc)
        return {**kwargs, self.STATUS_CODE_KWARG: status_code}

    def construct_response(self, exc: ExceptionType) -> ResponseType:
        """Construct the response to be returned."""
        content = self.prepare_response_content(exc)
        kwargs = self.prepare_response_kwargs(exc)
        return self.response_type(content, **kwargs)  # type: ignore

    def raise_exception_captured(self, exc: ExceptionType) -> typing.NoReturn:
        """Re-raise the captured exception as an `ExceptionCaptured` exception."""
        response = self.construct_response(exc)
        formatted_response = response
        if self.response_formatter:
            if iscoroutinefunction(self.response_formatter):
                formatted_response = self.run_sync(self.response_formatter, response)
            else:
                formatted_response = self.response_formatter(response)

        if formatted_response.status_code >= 500 and self.log_errors:  # type: ignore
            log_exception(exc, logger=self.logger)

        raise self.ExceptionCaptured(
            captive=exc,
            captor=self,
            response=formatted_response,  # type: ignore
        ) from exc  # Preserve exception context for easier debugging

    async def async_raise_exception_captured(
        self, exc: ExceptionType
    ) -> typing.NoReturn:
        """Re-raise the captured exception as an `ExceptionCaptured` exception."""
        response = await self.run_async(self.construct_response, exc)
        formatted_response = response
        if self.response_formatter:
            if iscoroutinefunction(self.response_formatter):
                formatted_response = await self.response_formatter(response)
            else:
                formatted_response = await self.run_async(
                    self.response_formatter, response
                )

        if formatted_response.status_code >= 500 and self.log_errors:  # type: ignore
            await self.run_async(log_exception, exc, logger=self.logger)
        raise self.ExceptionCaptured(
            captive=exc,
            captor=self,
            response=formatted_response,  # type: ignore
        ) from exc

    @typing.overload
    def add_callback(
        self,
        callback: ExceptionCallback[ExceptionType, P, R],
        priority: typing.Union[int, float] = 0,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None: ...

    @typing.overload
    def add_callback(
        self,
        callback: PrioritizedCallback[ExceptionType, P, R],
        priority: typing.Union[int, float] = 0,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None: ...

    # Sorting the callbacks by priority should be done on execution
    # to avoid unnecessary sorting on every callback addition, leading
    # to an O(n log n) complexity on every addition.
    def add_callback(
        self,
        callback: typing.Union[
            ExceptionCallback[ExceptionType, P, R],
            PrioritizedCallback[ExceptionType, P, R],
        ],
        priority: typing.Union[int, float] = 0,
        *args: typing.Any,
        **kwargs: typing.Any,
    ) -> None:
        """
        Add callbacks to be called on exception capture.

        Provides an opportunity to add clean-up logic in the event of an exception capture,
        or any additional processing that should be done.

        :param callback: The callback to be called
        :param priority: Priority of callback execution (higher runs first)
        :param args: The positional arguments to pass to the exception callback alongside the exception captured.
        :param kwargs: The keyword arguments to pass to the exception callback alongside the exception captured.

        Example:
        ```python

        @capture.enable
        def controller(*args, **kwargs):
            with capture(ValueError) as captor:
                # Lower priority callback runs second, although added first
                captor.add_callback(log_error, priority=50)
                # High priority callback runs first
                captor.add_callback(cleanup, priority=100)
                raise ValueError("test")
            ...
        ```
        """
        if not isinstance(callback, PrioritizedCallback):
            callback = PrioritizedCallback(
                callback=callback,
                priority=priority,
                args=args,
                kwargs=kwargs,
                _order=self._next_callback_order(),
            )
        else:
            # If it's already a PrioritizedCallback, reassign order for this instance
            callback = PrioritizedCallback(
                callback=callback.callback,
                priority=callback.priority,
                args=callback.args,
                kwargs=callback.kwargs,
                _order=self._next_callback_order(),
            )

        self.callbacks.append(callback)
        return None

    def execute_callbacks(self, exc: ExceptionType) -> None:
        """Execute callbacks in priority order"""
        for callback in sorted(self.callbacks):
            try:
                if callback.is_async:
                    self.run_sync(callback, exc)
                else:
                    callback(exc)
            except BaseException as e:
                if self.log_errors:
                    log_exception(e, logger=self.logger)
                pass
        return

    async def async_execute_callbacks(self, exc: ExceptionType) -> None:
        """Execute callbacks in priority order"""
        for callback in sorted(self.callbacks):
            try:
                if callback.is_async:
                    await callback(exc)
                else:
                    await self.run_async(callback, exc)
            except BaseException as e:
                if self.log_errors:
                    await self.run_async(log_exception, e, logger=self.logger)
                pass
        return

    def __enter__(self):
        if not self.response_type:
            raise RuntimeError(
                "response_type must be set before using as context manager"
            )
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type and self.verify_target(exc_type):
            self.execute_callbacks(exc_value)
            self.raise_exception_captured(exc_value)
        # Raise the exception if it is not of the target type(s)
        return False

    async def __aenter__(self):
        if not self.response_type:
            raise RuntimeError(
                "response_type must be set before using as context manager"
            )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_type and self.verify_target(exc_type):
            await self.async_execute_callbacks(exc_value)
            await self.async_raise_exception_captured(exc_value)
        # Raise the exception if it is not of the target type(s)
        return False

    def decorate_controller_func(
        self, controller_func: ControllerFunc[P, ResponseType]
    ) -> ControllerFunc[P, ResponseType]:
        # If the controller has been enabled for capture,
        # that means it has already been decorated
        # by the `enable` decorator, and is wrapped.
        # Hence, we decorate the wrapped controller instead
        if getattr(controller_func, CAPTURE_ENABLED_ATTR, False):
            wrapped_controller = getattr(controller_func, WRAPPED_CONTROLLER_ATTR)
            setattr(controller_func, WRAPPED_CONTROLLER_ATTR, self(wrapped_controller))
            return controller_func
        return super().decorate_controller_func(controller_func)

    @typing.overload
    @classmethod
    def enable(
        cls,
        controller: typing.Type[DjangoControllerClass[ResponseType]],
    ) -> typing.Type[DjangoControllerClass[ResponseType]]: ...

    @typing.overload
    @classmethod
    def enable(
        cls,
        controller: ControllerFunc[P, ResponseType],
    ) -> ControllerFunc[P, ResponseType]: ...

    @classmethod
    def enable(
        cls,
        controller: typing.Union[
            typing.Type[DjangoControllerClass[ResponseType]],
            ControllerFunc[P, ResponseType],
        ],
    ) -> typing.Union[
        typing.Type[DjangoControllerClass[ResponseType]],
        ControllerFunc[P, ResponseType],
    ]:
        """
        Enables the exception capture API on the decorated controller.

        Example:
        ```python
        @capture.enable
        def controller(request, *args, **kwargs):
            ...
            with capture.capture(ValueError, code=400) as captor:
                raise ValueError("Invalid value")
            ...
        ```

        Or;
        ```python
        @capture.capture(...)
        @capture.enable
        class MyController(BaseController):
            ...
        ```
        """
        if getattr(controller, CAPTURE_ENABLED_ATTR, False):
            return controller

        if inspect.isclass(controller):
            for method_name in controller.http_method_names:
                method_name = method_name.lower()
                method = getattr(controller, method_name, None)
                if not method:
                    continue
                setattr(controller, method_name, enable(method))
            return controller

        wrapper = None
        if iscoroutinefunction(controller):

            @functools.wraps(controller)
            async def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> ResponseType:
                try:
                    return await getattr(wrapper, WRAPPED_CONTROLLER_ATTR)(
                        *args, **kwargs
                    )
                except cls.ExceptionCaptured as exc:
                    return exc.response

            wrapper = sync_wrapper
        else:

            @functools.wraps(controller)
            def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> ResponseType:
                try:
                    return getattr(wrapper, WRAPPED_CONTROLLER_ATTR)(*args, **kwargs)
                except cls.ExceptionCaptured as exc:
                    return exc.response

            wrapper = async_wrapper

        setattr(wrapper, CAPTURE_ENABLED_ATTR, True)
        setattr(wrapper, WRAPPED_CONTROLLER_ATTR, controller)
        return wrapper


####### EXPORT ALIASES #######
capture = ExceptionCaptor
enable = ExceptionCaptor.enable


__all__ = [
    "ControllerContextDecorator",
    "ExceptionCaptor",
    "capture",
    "enable",
    "ExceptionCallback",
    "PrioritizedCallback",
]
