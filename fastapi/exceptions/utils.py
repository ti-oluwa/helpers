import typing
from starlette.exceptions import HTTPException
from starlette.websockets import WebSocketDisconnect, WebSocket
from starlette.requests import HTTPConnection


def raise_http_exception(
    connection: HTTPConnection,
    status_code: int,
    detail: str = "Oops! An error occurred.",
    headers: typing.Optional[typing.Dict[str, str]] = None,
):
    """
    Raises an HTTP exception with the provided status code and detail.

    :param connection: The HTTP connection.
    :param status_code: The status code to return.
    :param detail: The detail to return. Default is "Oops! An error occurred.".
    """
    if isinstance(connection, WebSocket):
        raise WebSocketDisconnect(code=status_code, reason=detail)
    raise HTTPException(
        status_code=status_code,
        detail=detail,
        headers=headers,
    )
