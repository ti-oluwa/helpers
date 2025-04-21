import typing
import asyncio
import importlib
import re
import functools
from collections.abc import Mapping
from starlette.types import ASGIApp, Receive, Scope, Send, Message
from starlette.requests import HTTPConnection, empty_send
from starlette.responses import Response
from starlette.datastructures import MutableHeaders
from starlette.concurrency import run_in_threadpool

from helpers.fastapi.config import settings
from .format import json_httpresponse_formatter, Formatter
from helpers.logging import log_exception


class FormatJSONResponseMiddleware:
    """
    Middleware to format JSON response data to a structured and consistent format (as defined by formatter).

    In settings.py:

    ```python
    RESPONSE_FORMATTER = {
        "formatter": "path.to.formatter_function", # Default formatter is used if not set
        "exclude": [r"^(?!/api).*$", ...] # Routes to exclude from formatting
    }
    ```
    """

    default_formatter: Formatter = json_httpresponse_formatter
    """The default response formatter."""
    setting_name = "RESPONSE_FORMATTER"
    """The name of the setting for the middleware in the helpers settings."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self.formatter = self.get_formatter()
        self.excluded_paths_patterns = [
            re.compile(path) for path in self.settings.get("exclude", [])
        ]
        self.enforce_format = self.settings.get("enforce_format", True) is True

    @functools.cached_property
    def settings(cls) -> Mapping[str, typing.Any]:
        middleware_settings = settings.get(cls.setting_name, {})
        if not isinstance(middleware_settings, Mapping):
            raise TypeError(
                f"settings.{cls.setting_name} should be a mapping not {type(middleware_settings).__name__}"
            )
        return middleware_settings

    def get_formatter(self) -> Formatter:
        """Return the response formatter."""
        formatter_path: str = self.settings.get("formatter", "default")

        if formatter_path.lower() == "default":
            formatter = type(self).default_formatter
        else:
            formatter = importlib.import_module(formatter_path)
            if not callable(formatter):
                raise TypeError("Response formatter must be a callable")

        return formatter

    def is_json_response(self, response: Response) -> bool:
        """
        Check if the response is a JSON response.

        :param response: The response object.
        :return: True if the response is a JSON response, False otherwise.
        """
        return response.headers.get("Content-Type", "").startswith("application/json")

    async def can_format(self, connection: HTTPConnection, response: Response) -> bool:
        """
        Check if the response can be formatted.

        :param connection: The connection object.
        :param response: The response object.
        :return: True if the response can be formatted, False otherwise.
        """
        if self.enforce_format is False or not self.is_json_response(response):
            return False

        request_path = "/" + connection.url.path.lstrip("/")
        for excluded_path_pattern in self.excluded_paths_patterns:
            if excluded_path_pattern.match(request_path):
                return False
        return True

    async def format(self, connection: HTTPConnection, response: Response) -> Response:
        """
        Format the response.

        :param connection: The connection object.
        :param response: The response object.
        :return: The formatted response object.
        """
        can_format = await self.can_format(connection, response)
        if not can_format:
            return response

        try:
            if asyncio.iscoroutinefunction(self.formatter):
                return await self.formatter(response)
            else:
                return await run_in_threadpool(self.formatter, response)  # type: ignore
        except Exception as exc:
            log_exception(exc)
            return response

    async def pre_format(
        self, connection: HTTPConnection, response: Response
    ) -> Response:
        """
        Should contain logic to be executed before formatting the response.
        """
        return response

    async def post_format(
        self, connection: HTTPConnection, formatted_response: Response
    ) -> Response:
        """
        Should contain logic to be executed after formatting the response.
        """
        return formatted_response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the connection."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope, receive)

        async def formatter(response: Response) -> Response:
            nonlocal connection
            pre_formatted_response = await self.pre_format(connection, response)
            formatted_response = await self.format(connection, pre_formatted_response)
            return await self.post_format(connection, formatted_response)

        responder = FormatResponder(app=self.app, formatter=formatter)
        await responder(scope, receive, send)


async def encode_headers(
    headers: typing.Mapping[str, str],
) -> typing.Sequence[typing.Tuple[bytes, bytes]]:
    return [(k.encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]


async def decode_headers(
    headers: typing.Sequence[typing.Tuple[bytes, bytes]],
) -> typing.MutableMapping[str, str]:
    return {k.decode("latin-1"): v.decode("latin-1") for k, v in headers}


class FormatResponder:
    def __init__(
        self,
        app: ASGIApp,
        formatter: typing.Callable[[Response], typing.Awaitable[Response]],
    ) -> None:
        self.app = app
        self.formatter = formatter
        self.send = empty_send
        self.response_started = False
        self.response_start_message = {}
        self.content_encoding_set = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.send_formatted)

    async def send_formatted(self, message: Message) -> None:
        # Delay sending the response event to the client until
        # the response is complete so that we can format the
        # response after which we can then send the response
        # event to the client in correct sequence.
        message_type = message["type"]
        if message_type == "http.response.start":
            self.response_start_message = message
            self.content_encoding_set = (
                "content-encoding" in self.response_start_message["headers"]
            )

        elif message_type == "http.response.body" and self.content_encoding_set:
            if not self.response_started:
                self.response_started = True
                await self.send(self.response_start_message)
            await self.send(message)

        elif message_type == "http.response.body" and not self.response_started:
            body = message.get("body", b"")
            more_body: bool = message.get("more_body", False)
            headers = MutableHeaders(raw=self.response_start_message["headers"])
            status_code = self.response_start_message["status"]
            response = Response(
                status_code=status_code,
                headers=headers,
                content=body,
            )
            response = await self.formatter(response)
            self.response_started = True
            await self.send(
                {
                    "type": "http.response.start",
                    "status": status_code,
                    "headers": response.headers.raw,
                }
            )
            await self.send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": more_body,
                }
            )
        elif message_type == "http.response.body":
            body = message.get("body", b"")
            if not body:
                await self.send(message)
                return

            headers = MutableHeaders(raw=self.response_start_message["headers"])
            status_code = self.response_start_message["status"]
            response = Response(
                status_code=status_code,
                headers=headers,
                content=body,
            )
            response = await self.formatter(response)
            message["body"] = response.body
            await self.send(message)
