import typing
import starlette.requests
import ipaddress


_Request = typing.TypeVar("_Request", bound=starlette.requests.Request)


def get_ip_address(
    request: _Request,
) -> typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
    """
    Returns the IP address of the request.

    :param request: The request object
    """
    x_forwarded_for = request.headers.get("x-forwarded-for") or request.headers.get(
        "remote-addr"
    )
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.client.host
    return ipaddress.ip_address(ip)
