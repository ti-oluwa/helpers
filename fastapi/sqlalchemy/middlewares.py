import fastapi

from .setup import get_session, get_async_session


async def AsyncSessionMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to attach an async DB session to the request object.

    Automatically commits the session to the database and closes it after the request is processed.
    Uncommitted changes are rolled back if an exception occurs, while processing the request.

    Set the `ATOMIC_REQUESTS` setting to `True` to make the session commit once, at the end of the request,
    Even if the session is committed multiple times in the view/endpoint.
    """
    async with next(get_async_session()) as session:
        request.state.db_session = session
        response = await call_next(request)
        return response


async def SessionMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to attach a DB session to the request object.

    Automatically commits the session to the database and closes it after the request is processed.
    Uncommitted changes are rolled back if an exception occurs, while processing the request.

    Set the `ATOMIC_REQUESTS` setting to `True` to make the session commit once, at the end of the request,
    Even if the session is committed multiple times in the view/endpoint.
    """
    with next(get_session()) as session:
        request.state.db_session = session
        response = await call_next(request)
        return response
