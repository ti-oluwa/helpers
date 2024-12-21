import asyncio
import functools
import inspect
import typing
from typing_extensions import Unpack, ParamSpec
import fastapi
import fastapi.params
import starlette.requests

from .base import (
    Function,
    CoroutineFunction,
    _HTTPConnection,
    ConnectionIdentifier,
    ConnectionThrottledHandler,
)
from .throttles import BaseThrottle, HTTPThrottle, NoLimit
from helpers.fastapi.utils.sync import sync_to_async
from helpers.generics.utils.functions import add_parameter_to_signature


_P = ParamSpec("_P")
_Q = ParamSpec("_Q")
_R = typing.TypeVar("_R")
_S = typing.TypeVar("_S")

Decorated = typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]]
Dependency = typing.Union[Function[_P, _R], CoroutineFunction[_P, _R]]
_Throttle = typing.TypeVar("_Throttle", bound=BaseThrottle)


class ThrottleKwargs(typing.TypedDict):
    """Keyword arguments for creating a throttle"""

    limit: int
    """Maximum number of times the route can be accessed within specified time period."""
    milliseconds: int
    """Time frame in milliseconds."""
    seconds: int
    """Time frame in seconds."""
    minutes: int
    """Time frame in minutes."""
    hours: int
    """Time frame in hours."""
    connection_throttled_handler: typing.Optional[
        ConnectionThrottledHandler[_HTTPConnection]
    ]
    """Handler to call when the client connection is throttled."""


class DecoratorDepends(typing.Generic[_P, _Q, _R, _S], fastapi.params.Depends):
    """
    `fastapi.params.Depends` subclass that allows instances to be used as decorators.

    Instances use `dependency_decorator` to apply the dependency to the decorated object,
    while still allowing usage as regular FastAPI dependencies.

    `dependency_decorator` is a callable that takes the decorated object and an optional dependency
    and returns the decorated object with/without the dependency applied.

    Think of the `dependency_decorator` as a chef that mixes the sauce (dependency)
    with the dish (decorated object), making a dish with the sauce or without it.
    """

    def __init__(
        self,
        dependency_decorator: Function[
            [Decorated[_Q, _S], typing.Optional[Dependency[_P, _R]]],
            Decorated[_Q, _S],
        ],
        dependency: typing.Optional[Dependency[_P, _R]] = None,
        *,
        use_cache: bool = True,
    ):
        self.dependency_decorator = dependency_decorator
        super().__init__(dependency, use_cache=use_cache)

    def __call__(self, decorated: Decorated[_Q, _S]):
        return self.dependency_decorator(decorated, self.dependency)


# Is this worth it? Just because of the `throttle` decorator?
def _wrap_route(
    route: Decorated[_Q, _S],
    throttle: _Throttle,
) -> Decorated[_Q, _S]:
    """
    Create an wrapper that applies throttling to an route
    by wrapping the route such that the route depends on the throttle.

    :param route: The route to wrap.
    :param throttle: The throttle to apply to the route.
    :return: The wrapper that enforces the throttle on the route.
    """
    # * This approach is necessary because FastAPI does not support dependencies
    # * that are not in the signature of the route function.

    # Use unique (throttle) dependency parameter name to avoid conflicts
    # with other dependencies that may be applied to the route, or in the case
    # of nested use of this wrapper function.
    throttle_dep_param_name = f"_{id(throttle)}_throttle"

    # We need the throttle dependency to be the first parameter of the route
    # So that the rate limit check is done before any other operations or dependencies
    # are resolved/executed, improving the efficiency of implementation.
    if asyncio.iscoroutinefunction(route):
        wrapper_code = f"""
async def route_wrapper(
    {throttle_dep_param_name}: typing.Annotated[typing.Any, fastapi.Depends(throttle)],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _R:
    return await route(*args, **kwargs)
"""
    else:
        wrapper_code = f"""
def route_wrapper(
    {throttle_dep_param_name}: typing.Annotated[typing.Any, fastapi.Depends(throttle)],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> _R:
    return route(*args, **kwargs)
"""

    local_namespace = {
        "throttle": throttle,
    }
    global_namespace = {
        **globals(),
        "route": route,
    }
    exec(
        wrapper_code,
        global_namespace,
        local_namespace,
    )
    route_wrapper = local_namespace["route_wrapper"]
    route_wrapper = functools.wraps(route)(route_wrapper)
    # The resulting function from applying `functools.wraps(route)` on `route_wrapper`
    # would not have the throttle dependency in its signature, although it is present in `route_wrapper`'s definition,
    # because the result of `functools.wraps` assumes the signature of the original function (route in this case).

    # Since the original/wrapped function does not have the throttle dependency in its signature,
    # the throttle dependency will not be recognized/regarded by FastAPI, as FastAPI
    # uses the signature of the function to determine the params, hence the dependencies of the function.

    # So, we update the signature of the wrapper to include the throttle dependency
    route_wrapper = add_parameter_to_signature(
        func=route_wrapper,
        parameter=inspect.Parameter(
            name=throttle_dep_param_name,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=typing.Annotated[typing.Any, fastapi.Depends(throttle)],
        ),
        index=0,  # Since the throttle dependency was added as the first parameter
    )
    return route_wrapper


def _throttle_route(
    route: Decorated[_Q, _S],
    throttle: _Throttle,
) -> Decorated[_Q, _S]:
    """
    Returns wrapper that applies throttling to the given route
    by wrapping the route such that the route depends on the throttle.

    :param route: The route to be throttled.
    :param throttle: The throttle to apply to the route.
    """
    wrapper = _wrap_route(route, throttle)
    return wrapper


def throttle(
    route: typing.Optional[Decorated[_P, _R]] = None,
    /,
    *,
    identifier: typing.Optional[ConnectionIdentifier[_HTTPConnection]] = None,
    throttle_type: typing.Type[_Throttle] = HTTPThrottle,
    **throttle_kwargs: Unpack[ThrottleKwargs],
):
    """
    Route dependency/decorator that throttles connections to a route
    based on the defined client identifier.

    :param route: Decorated route to throttle.
    :param identifier: A callable that generates a unique identifier for the client. Defaults to the client IP.
    :param throttle_type: The throttle type to use. Defaults to `HTTPThrottle`.
    :param throttle_kwargs: Keyword arguments to be used to instantiate the throttle type.

    Usage Examples:
    ```python
    import fastapi

    router = fastapi.APIRouter(
        dependencies=[
            throttle(limit=1, seconds=3)
        ]
    )

    @router.get("/limited1")
    async def limited_route1():
        return {"message": "Limited route"}

    @router.get("/limited2")
    async def limited_route2():
        return {"message": "Limited route 2"}
    ```

    Or;

    ```python
    import fastapi

    router = fastapi.APIRouter()

    @router.get(
        "/limited",
        dependencies=[
            throttle(limit=1, seconds=3),
        ]
    )
    async def limited_route():
        return {"message": "Limited route"}
    ```

    Or;

    ```python
    import fastapi

    router = fastapi.APIRouter()

    @router.get("/limited")
    @throttle(limit=1, seconds=3)
    async def limited_route():
        return {"message": "Limited route"}
    ```
    """
    connection_throttled_handler = throttle_kwargs.pop(
        "connection_throttled_handler", None
    )
    if connection_throttled_handler and not asyncio.iscoroutinefunction(
        connection_throttled_handler
    ):
        throttle_kwargs["connection_throttled_handler"] = sync_to_async(
            connection_throttled_handler
        )

    if identifier and not asyncio.iscoroutinefunction(identifier):
        identifier = sync_to_async(identifier)

    throttle = throttle_type(identifier=identifier, **throttle_kwargs)
    decorator_dependency = DecoratorDepends(
        dependency_decorator=_throttle_route,
        dependency=throttle,
    )
    if route is not None:
        decorated = decorator_dependency(route)
        return decorated
    return decorator_dependency


# ---------- CLIENT IDENTIFIERS ---------- #


def get_referrer(connection: _HTTPConnection) -> str:
    return connection.headers.get("referer", "") or connection.headers.get("origin", "")


def connection_user_agent_identifier(connection: _HTTPConnection) -> str:
    return connection.headers.get("user-agent", "") + ":" + connection.scope["path"]


# ---------- CUSTOM THROTTLES ---------- #


def referrer_throttle(
    referrer: typing.Union[str, typing.List[str]],
    **throttle_kwargs: Unpack[ThrottleKwargs],
):
    """
    Throttles request connections based on the referrer of the request.

    This throttle is useful for limiting request connections referred from specific sources/origins.

    :param referrer: The referrer/origin(s) to limit connections from.
    :param throttle_kwargs: Keyword arguments to be used to instantiate the throttle type.
    """
    if isinstance(referrer, str):
        referrer = [
            referrer,
        ]
    referrer = set(referrer)

    def referrer_identifier(request: starlette.requests.Request) -> str:
        nonlocal referrer

        request_referrer = get_referrer(request)
        if request_referrer not in referrer:
            raise NoLimit()
        return request_referrer + ":" + request.scope["path"]

    return throttle(
        identifier=referrer_identifier,
        throttle_type=HTTPThrottle,
        **throttle_kwargs,
    )


user_agent_throttle = functools.partial(
    throttle, identifier=connection_user_agent_identifier
)
"""Throttle route connections based on the user agent."""


__all__ = [
    "throttle",
    "referrer_throttle",
    "user_agent_throttle",
]
