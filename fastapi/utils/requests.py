import typing
from starlette.requests import HTTPConnection
import ipaddress


_HTTPConnection = typing.TypeVar("_HTTPConnection", bound=HTTPConnection)

def get_ip_address(
    connection: _HTTPConnection,
) -> typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
    """
    Returns the IP address of the connection client.

    :param connection: The HTTP connection
    """
    x_forwarded_for = connection.headers.get("x-forwarded-for") or connection.headers.get(
        "remote-addr"
    )
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = connection.client.host
    return ipaddress.ip_address(ip)
