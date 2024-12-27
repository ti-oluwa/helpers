import inspect
import typing
import fastapi
import re

from helpers.fastapi.config import settings
from helpers.fastapi.utils.requests import get_ip_address
from helpers.generics.utils.module_loading import import_string


def convert_to_regex(host_pattern: str) -> str:
    """
    Converts a Django-style wildcard host pattern into a regex.
    For example:
      "*.example.com" -> r"^.*\\.example\\.com$"
    """
    if host_pattern == "*":
        return r".*"  # Match everything
    host_pattern = re.escape(host_pattern).replace(r"\*", ".*")
    return rf"^{host_pattern}$"


async def AllowedHostsMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to check if the request host is allowed.

    :param request: FastAPI request object
    :param call_next: Next middleware in the chain
    """
    hostname = request.url.hostname
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", [])
    if not (allowed_hosts and hostname):
        response = await call_next(request)
        return response

    for host in allowed_hosts:
        if re.match(convert_to_regex(host), hostname):
            response = await call_next(request)
            return response
    return fastapi.responses.JSONResponse(
        status_code=403, content={"detail": "Access disallowed."}
    )


async def AllowedIPsMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to check if the request IP is allowed.

    :param request: FastAPI request object
    :param call_next: Next middleware in the chain
    """
    request_ip = get_ip_address(request)
    allowed_ips = getattr(settings, "ALLOWED_IPS", [])
    if not (allowed_ips and request_ip):
        response = await call_next(request)
        return response

    for ip in allowed_ips:
        if re.match(convert_to_regex(ip), request_ip.exploded):
            response = await call_next(request)
            return response
    return fastapi.responses.JSONResponse(
        status_code=403, content={"detail": "Access disallowed."}
    )


async def HostBlacklistMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to check if the request host is blacklisted.

    :param request: FastAPI request object
    :param call_next: Next middleware in the chain
    """
    hostname = request.url.hostname
    blacklisted_hosts: typing.Optional[typing.List[str]] = getattr(
        settings, "BLACKLISTED_HOSTS", None
    )
    if not blacklisted_hosts or not hostname:
        response = await call_next(request)
        return response

    for host in blacklisted_hosts:
        if re.match(convert_to_regex(host), hostname):
            return fastapi.responses.JSONResponse(
                status_code=403, content={"detail": "Access denied."}
            )
    return await call_next(request)


async def IPBlacklistMiddleware(request: fastapi.Request, call_next):
    """
    Middleware to check if the request IP is blacklisted.

    :param request: FastAPI request object
    :param call_next: Next middleware in the chain
    """
    blacklisted_ips: typing.Optional[typing.List[str]] = getattr(
        settings, "BLACKLISTED_IPS", None
    )
    if not blacklisted_ips:
        response = await call_next(request)
        return response

    for ip in blacklisted_ips:
        if request.client.host == ip:
            return fastapi.responses.JSONResponse(
                status_code=403, content={"detail": "Access denied."}
            )
    response = await call_next(request)
    return response


def middlewares():
    """
    Yield all middleware defined in the settings.
    """
    middleware: typing.Optional[typing.List[str]] = settings.get("MIDDLEWARE", None)
    if not middleware:
        return

    for middleware_path in reversed(middleware):
        if isinstance(middleware_path, str):
            middleware = import_string(middleware_path)

        if not callable(middleware):
            raise TypeError(f"Middleware {middleware} is not a callable.")
        yield middleware


def apply_middleware(app: fastapi.FastAPI) -> fastapi.FastAPI:
    """
    Apply all middleware to the FastAPI app.
    """
    for middleware in middlewares():
        if inspect.isclass(middleware):
            app.add_middleware(middleware)
        else:
            app.middleware("http")(middleware)
    return app
