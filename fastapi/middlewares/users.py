from starlette.requests import HTTPConnection

from helpers.fastapi.models.users import AbstractBaseUser, AnonymousUser


async def ConnectedUserMiddleware(connection: HTTPConnection, call_next):
    """
    Middleware that adds the connected user to the connection state.

    `connection.state.user` will be an AbstractBaseUser instance.

    :param connection: `starlette.requests.HTTPConnection` instance.
    :param call_next: Next middleware in the chain
    """
    connected_user = getattr(connection.state, "user", None)
    if not isinstance(connected_user, AbstractBaseUser):
        connection.state.user = AnonymousUser()
    
    response = await call_next(connection)
    return response
