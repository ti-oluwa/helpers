"""
HTTP connection and connected user access control dependencies
"""

import typing
import asyncio
from starlette.requests import HTTPConnection

from helpers.fastapi.utils.sync import sync_to_async
from helpers.fastapi.exceptions.utils import raise_http_exception
from .connections import connected_user, AnyDBSession, _DBSession, _UserModel
from . import Dependency


_T = typing.TypeVar("_T")
_AccessChecker = typing.Callable[
    [_T, typing.Optional[_DBSession]],
    typing.Union[bool, typing.Coroutine[None, None, bool]],
]
_ResultHandler = typing.Callable[
    [_T],
    typing.Union[
        typing.Any, typing.Coroutine[None, None, typing.Union[_T, typing.Any]]
    ],
]


def access_control(
    access_checker: _AccessChecker[HTTPConnection, _DBSession],
    *,
    status_code: int = 403,
    message: str = "Access Denied!",
    raise_access_denied: typing.Union[
        typing.Callable[[HTTPConnection, int, str], typing.NoReturn],
        typing.Literal[False],
        None,
    ] = raise_http_exception,
    result_handler: typing.Optional[_ResultHandler[HTTPConnection]] = None,
):
    """
    Connection access control dependency factory.

    Returns a dependency that checks if the http connection is allowed to access to the resource
    based on the provided connection `access_checker` function.

    :param access_checker: A callable that takes the connection object and returns a boolean
        indicating if it is allowed access or not.

    :param status_code: The status code to return if the connection is disallowed access.
        Default is `HTTP_403_FORBIDDEN`.

    :param message: The message to return if the connection is disallowed access.

    :param raise_access_denied: A callable that raises an exception with the provided status code and message.
        If not provided or falsy, no exception is raised and the connection is returned by the dependency.

        Setting this to falsy value can be useful when you want changes made to be made to the connection object
        by the access checker to remain if the connection is allowed, but not if it is denied,
        without raising an exception. There by allowing the connection to be served, with or without the required access.

    :param result_handler: A callable that takes the connection object and returns a result.
        If provided, the result is returned by the dependency instead of the connection object.

    :return: A dependency that checks if the connection is allowed access to the resource.
    """

    async def access_control_dependency(
        connection: HTTPConnection, session: AnyDBSession
    ):
        if not asyncio.iscoroutinefunction(access_checker):
            has_access = await sync_to_async(access_checker)(connection, session)
        else:
            has_access = await access_checker(connection, session)

        if not has_access and raise_access_denied:
            raise_access_denied(connection, status_code, message)

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
    access_checker: _AccessChecker[_UserModel, _DBSession],
    *,
    get_user: typing.Callable[..., typing.Optional[_UserModel]] = connected_user,
    status_code: int = 403,
    message: str = "Access Denied!",
    raise_access_denied: typing.Union[
        typing.Callable[[HTTPConnection, int, str], typing.NoReturn],
        typing.Literal[False],
        None,
    ] = raise_http_exception,
    result_handler: typing.Optional[_ResultHandler[_UserModel]] = None,
):
    """
    Connection access control dependency factory.

    Returns a dependency that checks if the connected user is allowed access to the resource
    based on the provided user `access_checker` function.

    :param access_checker: A callable that takes the connected user object and returns a boolean
        indicating if the user has access to the resource or not.

    :param get_user: A callable that returns the connected user object, usually from the request/connection.
        Default is `connected_user`. This is used as a sub dependency to get the connected user.

    :param status_code: The status code to return if the user is disallowed access.
        Default is `HTTP_403_FORBIDDEN`.

    :param message: The message to return if the user is disallowed access.

    :param raise_access_denied: A callable that raises an exception with the provided status code and message.
        If not provided or falsy, no exception is raised and the user is returned by the dependency.

        Setting this to a falsy value be can useful when you want changes made to be made to the user object
        by the access checker to remain if the user is allowed, but not if it is denied,
        without raising an exception. There by allowing the user to be served, with or without the required access.

    :param result_handler: A callable that takes the user object and returns a result.
        If provided, the result is returned by the dependency instead of the user object.

    :return: A dependency that checks if the user is allowed access to the resource.
    """

    async def access_control_dependency(
        connection: HTTPConnection,
        user: typing.Annotated[typing.Optional[_UserModel], Dependency(get_user)],
        session: AnyDBSession,
    ):
        if user:
            if not asyncio.iscoroutinefunction(access_checker):
                has_access = await sync_to_async(access_checker)(user, session)
            else:
                has_access = await access_checker(user, session)
        else:
            has_access = False

        if not has_access and raise_access_denied:
            raise_access_denied(connection, status_code, message)

        if user and result_handler:
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
"""
Connection access control dependency that requires the connected user to be authenticated.

:raises HTTPException: If the connected user is not authenticated.
:return: The connected user if authenticated.
"""
AuthenticatedUser = typing.Annotated[_UserModel, authenticated_user_only]
"""
Annotated connection access control dependency type that requires the connected user to be authenticated.

:raises HTTPException: If the connected user is not authenticated.
:return: The connected user if authenticated.
"""


active_user_only = user_access_control(
    lambda user, _: getattr(user, "is_active", False),
    get_user=authenticated_user_only,  # type: ignore
)
"""
Access control dependency that requires the connected user to be (authenticated and) active.

:raises HTTPException: If the connected user is not active.
:return: The connected user if active.
"""
ActiveUser = typing.Annotated[_UserModel, active_user_only]
"""
Annotated connection access control dependency type that requires the connected user to be (authenticated and) active.

:raises HTTPException: If the connected user is not active.
:return: The connected user if active.
"""


admin_user_only = user_access_control(
    lambda user, _: getattr(user, "is_admin", False),
    get_user=active_user_only,  # type: ignore
)
"""
Access control dependency that requires the connected user to be (authenticated and) an admin.

:raises HTTPException: If the connected user is not an admin.
:return: The connected user if an admin.
"""
AdminUser = typing.Annotated[_UserModel, admin_user_only]
"""
Annotated connection access control dependency type that requires the connected user to be (authenticated and) an admin.

:raises HTTPException: If the connected user is not an admin.
:return: The connected user if an admin.
"""


staff_user_only = user_access_control(
    lambda user, _: getattr(user, "is_staff", False),
    get_user=active_user_only,  # type: ignore
)
"""
Access control dependency that requires the connected user to be (authenticated and) a staff.

:raises HTTPException: If the connected user is not a staff.
:return: The connected user if a staff.
"""
StaffUser = typing.Annotated[_UserModel, staff_user_only]
"""
Annotated dependency type that requires the connected user to be (authenticated and) a staff.

:raises HTTPException: If the connected user is not a staff.
:return: The connected user if a staff.
"""
