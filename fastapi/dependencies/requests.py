import typing
import fastapi

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.fastapi.models.users import AbstractBaseUser


_DBSession = typing.Union[Session, AsyncSession]


def db_session(request: fastapi.Request):
    """
    Returns the database session for the request.

    This is meant be used along with the `SessionMiddleware` or `AsyncSessionMiddleware` middleware.
    """
    return getattr(request.state, "db_session", None)


RequestDBSession = typing.Annotated[
    typing.Optional[typing.Union[_DBSession]], fastapi.Depends(db_session)
]
"""FastAPI dependency annotation used to inject the request's database session."""


def request_user(request: fastapi.Request):
    """
    Returns the user associated with the request.

    This is meant be used along with the `RequestUserMiddleware` middleware.
    """
    return request.state.user


RequestUser = typing.Annotated[
    typing.Union[AbstractBaseUser], fastapi.Depends(request_user)
]
"""FastAPI dependency annotation used to inject the request user."""
