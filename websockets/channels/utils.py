import typing
from django.utils.module_loading import import_string

from helpers.config import settings


def get_middleware() -> typing.List[str]:
    """Returns the list of middlewares defined in the helpers settings"""
    middlewares: typing.List[str] = settings.WEBSOCKETS["CHANNELS"]["MIDDLEWARE"]
    return middlewares


def apply_middleware(router, middleware: typing.List[str]):
    """
    Applies the middleware to the router
    """
    for path in middleware:
        middleware_cls = import_string(path)
        router = middleware_cls(router)
    return router


async def async_reject_connection(send, message: str, code: int) -> None:
    """Rejects the connection with the given message and code"""
    await send({"type": "websocket.close", "code": code, "reason": message})
    return None


def reject_connection(send, message: str, code: int) -> None:
    """Rejects the connection with the given message and code"""
    send({"type": "websocket.close", "code": code, "reason": message})
    return None
