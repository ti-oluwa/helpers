import typing
import asyncio
import fastapi
import fastapi.params
from starlette.concurrency import run_in_threadpool

from helpers.fastapi.models.users import AbstractBaseUser
from .requests import request_user, RequestDBSession, _DBSession
from .import Dependency


_T = typing.TypeVar("_T")
_AccessChecker = typing.Callable[
    [_T, typing.Optional[_DBSession]],
    typing.Union[bool, typing.Coroutine[None, None, bool]],
]
_ResultHandler = typing.Callable[
    [_T],
    typing.Union[typing.Any, typing.Coroutine[None, None, typing.Any]],
]


def request_access_control(
    access_checker: _AccessChecker[fastapi.Request],
    /,
    *,
    status_code: int = fastapi.status.HTTP_403_FORBIDDEN,
    message: str = "Access Denied!",
    result_handler: typing.Optional[_ResultHandler[fastapi.Request]] = None,
):
    """
    Returns a (request) dependency that checks if the request has access to the resource
    based on the provided `access_checker` function.

    :param access_checker: A callable that takes a request object and returns a boolean
        indicating if the request has access to the resource or not.
    :param status_code: The status code to return if the request does not have access.
        Default is `HTTP_403_FORBIDDEN`.
    :param message: The message to return if the request does not have access.
    :return: A dependency that checks if the request has access to the resource.
    """

    async def access_control_dependency(
        request: fastapi.Request, session: RequestDBSession
    ):
        if not asyncio.iscoroutinefunction(access_checker):
            has_access = await run_in_threadpool(access_checker, request, session)
        else:
            has_access = await access_checker(request, session)

        if not has_access:
            raise fastapi.HTTPException(status_code=status_code, detail=message)

        if result_handler:
            if not asyncio.iscoroutinefunction(result_handler):
                result = await run_in_threadpool(result_handler, request)
            else:
                result = await result_handler(request)
        else:
            result = request
        return result

    return Dependency(access_control_dependency)


def user_access_control(
    access_checker: _AccessChecker[AbstractBaseUser],
    /,
    *,
    get_user: typing.Callable[..., AbstractBaseUser] = request_user,
    status_code: int = fastapi.status.HTTP_403_FORBIDDEN,
    message: str = "Access Denied!",
    result_handler: typing.Optional[_ResultHandler[AbstractBaseUser]] = None,
):
    """
    Returns a (user) dependency that checks if the user has access to the resource
    based on the provided user `access_checker` function.

    :param access_checker: A callable that takes a user object and returns a boolean
        indicating if the user has access to the resource or not.
    :param get_user: A callable that returns the user object from the request.
        Default is `request_user`.
    :param status_code: The status code to return if the user does not have access.
        Default is `HTTP_403_FORBIDDEN`.
    :param message: The message to return if the user does not have access.
    :return: A dependency that checks if the user has access to the resource.
    """

    async def access_control_dependency(
        user: typing.Annotated[AbstractBaseUser, Dependency(get_user)],
        session: RequestDBSession,
    ):
        if not asyncio.iscoroutinefunction(access_checker):
            has_access = await run_in_threadpool(access_checker, user, session)
        else:
            has_access = await access_checker(user, session)

        if not has_access:
            raise fastapi.HTTPException(status_code=status_code, detail=message)

        if result_handler:
            if not asyncio.iscoroutinefunction(result_handler):
                result = await run_in_threadpool(result_handler, user)
            else:
                result = await result_handler(user)
        else:
            result = user

        return result

    return Dependency(access_control_dependency)


authenticated_user_only = user_access_control(
    lambda user, _: user.is_authenticated, message="Authentication Required!"
)
"""Access control dependency that requires the user to be authenticated."""
AuthenticatedUser = typing.Annotated[AbstractBaseUser, authenticated_user_only]
"""Annotated dependency type that requires the user to be authenticated."""


active_user_only = user_access_control(
    lambda user, _: user.is_active, get_user=authenticated_user_only
)
"""Access control dependency that requires the user to be (authenticated and) active."""
ActiveUser = typing.Annotated[AbstractBaseUser, active_user_only]
"""Annotated dependency type that requires the user to be (authenticated and) active."""


admin_user_only = user_access_control(
    lambda user, _: user.is_admin, get_user=active_user_only
)
"""Access control dependency that requires the user to be (authenticated and) an admin."""
AdminUser = typing.Annotated[AbstractBaseUser, admin_user_only]
"""Annotated dependency type that requires the user to be (authenticated and) an admin."""


staff_user_only = user_access_control(
    lambda user, _: user.is_staff, get_user=active_user_only
)
"""Access control dependency that requires the user to be (authenticated and) a staff user."""
StaffUser = typing.Annotated[AbstractBaseUser, staff_user_only]
"""Annotated dependency type that requires the user to be (authenticated and) a staff user."""
