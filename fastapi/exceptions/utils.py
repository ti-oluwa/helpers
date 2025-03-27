from starlette.exceptions import HTTPException
from starlette.websockets import WebSocketDisconnect, WebSocket
from starlette.requests import HTTPConnection


def raise_http_exception(
    connection: HTTPConnection,
    status_code: int,
    message: str = "Oops! An error occurred.",
):
    """
    Raises an HTTP exception with the provided status code and message.

    :param connection: The HTTP connection.
    :param status_code: The status code to return.
    :param message: The message to return. Default is "Oops! An error occurred.".
    """
    if isinstance(connection, WebSocket):
        raise WebSocketDisconnect(code=status_code, reason=message)
    raise HTTPException(status_code=status_code, detail=message)
