"""
HTTP connection and connected user access control dependencies
"""

import typing
import asyncio
from starlette.requests import HTTPConnection
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocket, WebSocketDisconnect

from helpers.fastapi.utils.sync import sync_to_async
from helpers.fastapi.models.users import AbstractBaseUser
from .connections import connected_user, DBSession, _DBSession
from . import Dependency


_T = typing.TypeVar("_T")
_AccessChecker = typing.Callable[
    [_T, typing.Optional[_DBSession]],
    typing.Union[bool, typing.Coroutine[None, None, bool]],
]
_ResultHandler = typing.Callable[
    [_T],
    typing.Union[typing.Any, typing.Coroutine[None, None, typing.Any]],
]


def raise_access_denied(
    connection: HTTPConnection,
    *,
    status_code: int,
    message: str = "Access Denied!",
):
    """
    Raises an HTTP exception with the provided status code and message.

    :param connection: The HTTP connection.
    :param status_code: The status code to return. Default is `HTTP_403_FORBIDDEN`.
    :param message: The message to return. Default is "Access Denied!".
    """
    if isinstance(connection, WebSocket):
        raise WebSocketDisconnect(code=status_code, reason=message)
    raise HTTPException(status_code=status_code, detail=message)


def access_control(
    access_checker: _AccessChecker[HTTPConnection],
    *,
    status_code: int = 403,
    message: str = "Access Denied!",
    result_handler: typing.Optional[_ResultHandler[HTTPConnection]] = None,
):
    """
    Returns a dependency that checks if the http connection is allowed to access to the resource
    based on the provided connection `access_checker` function.

    :param access_checker: A callable that takes the connection object and returns a boolean
        indicating if it is allowed access or not.
    :param status_code: The status code to return if the connection is disallowed access.
        Default is `HTTP_403_FORBIDDEN`.
    :param message: The message to return if the connection is disallowed access.
    :return: A dependency that checks if the connection is allowed access to the resource.
    """

    async def access_control_dependency(connection: HTTPConnection, session: DBSession):
        if not asyncio.iscoroutinefunction(access_checker):
            has_access = await sync_to_async(access_checker)(connection, session)
        else:
            has_access = await access_checker(connection, session)

        if not has_access:
            raise_access_denied(connection, status_code=status_code, message=message)

        if result_handler:
            if not asyncio.iscoroutinefunction(result_handler):
                result = await sync_to_async(result_handler)(connection)
            else:
                result = await result_handler(connection)
        else:
            result = connection
        return result

    return Dependency(access_control_dependency)


def user_access_control(
    access_checker: _AccessChecker[AbstractBaseUser],
    *,
    get_user: typing.Callable[..., AbstractBaseUser] = connected_user,
    status_code: int = 403,
    message: str = "Access Denied!",
    result_handler: typing.Optional[_ResultHandler[AbstractBaseUser]] = None,
):
    """
    Returns a dependency that checks if the connected user is allowed access to the resource
    based on the provided user `access_checker` function.

    :param access_checker: A callable that takes the connected user object and returns a boolean
        indicating if the user has access to the resource or not.
    :param get_user: A callable that returns the connected user object.
        Default is `connected_user`.
    :param status_code: The status code to return if the user is disallowed access.
        Default is `HTTP_403_FORBIDDEN`.
    :param message: The message to return if the user is disallowed access.
    :return: A dependency that checks if the user is allowed access to the resource.
    """

    async def access_control_dependency(
        connection: HTTPConnection,
        user: typing.Annotated[AbstractBaseUser, Dependency(get_user)],
        session: DBSession,
    ):
        if not asyncio.iscoroutinefunction(access_checker):
            has_access = await sync_to_async(access_checker)(user, session)
        else:
            has_access = await access_checker(user, session)

        if not has_access:
            raise_access_denied(connection, status_code=status_code, message=message)

        if result_handler:
            if not asyncio.iscoroutinefunction(result_handler):
                result = await sync_to_async(result_handler)(user)
            else:
                result = await result_handler(user)
        else:
            result = user

        return result

    return Dependency(access_control_dependency)


authenticated_user_only = user_access_control(
    lambda user, _: user.is_authenticated, message="Authentication Required!"
)
"""Access control dependency that requires the connected user to be authenticated."""
AuthenticatedUser = typing.Annotated[AbstractBaseUser, authenticated_user_only]
"""Annotated dependency type that requires the user to be authenticated."""


active_user_only = user_access_control(
    lambda user, _: user.is_active, get_user=authenticated_user_only
)
"""Access control dependency that requires the connected user to be (authenticated and) active."""
ActiveUser = typing.Annotated[AbstractBaseUser, active_user_only]
"""Annotated dependency type that requires the connected user to be (authenticated and) active."""


admin_user_only = user_access_control(
    lambda user, _: user.is_admin, get_user=active_user_only
)
"""Access control dependency that requires the connected user to be (authenticated and) an admin."""
AdminUser = typing.Annotated[AbstractBaseUser, admin_user_only]
"""Annotated dependency type that requires the connected user to be (authenticated and) an admin."""


staff_user_only = user_access_control(
    lambda user, _: user.is_staff, get_user=active_user_only
)
"""Access control dependency that requires the connected user to be (authenticated and) a staff."""
StaffUser = typing.Annotated[AbstractBaseUser, staff_user_only]
"""Annotated dependency type that requires the connected user to be (authenticated and) a staff."""
