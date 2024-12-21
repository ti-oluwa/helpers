import typing
import fastapi
from starlette.requests import HTTPConnection

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from helpers.fastapi.models.users import AbstractBaseUser


_DBSession = typing.Union[Session, AsyncSession]


def db_session(connection: HTTPConnection) -> typing.Optional[_DBSession]:
    """
    Returns the database session for the HTTP connection.

    This is meant be used along with the `SessionMiddleware` or `AsyncSessionMiddleware` middleware.
    """
    return getattr(connection.state, "db_session", None)


DBSession = typing.Annotated[
    typing.Optional[_DBSession], fastapi.Depends(db_session)
]
"""FastAPI dependency annotation used to inject the HTTP connection's database session."""


def connected_user(connection: HTTPConnection) -> typing.Optional[AbstractBaseUser]:
    """
    Returns the user associated with the connection.

    This is meant be used along with the `ConnectedUserMiddleware` middleware.
    """
    return getattr(connection.state, "user", None)


User = typing.Annotated[
    typing.Optional[AbstractBaseUser], fastapi.Depends(connected_user)
]
"""FastAPI dependency annotation used to inject the HTTP connection user."""
