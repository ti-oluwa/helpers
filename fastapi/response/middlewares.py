import asyncio
import collections.abc
import importlib
import re
import functools
from typing import List
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool

from helpers.fastapi.config import settings
from .format import json_httpresponse_formatter, Formatter
from helpers.logging import log_exception


class FormatJSONResponseMiddleware(BaseHTTPMiddleware):
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

    default_formatter = json_httpresponse_formatter
    """The default response formatter."""
    setting_name = "RESPONSE_FORMATTER"
    """The name of the setting for the middleware in the helpers settings."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.formatter = type(self).get_formatter()

    @classmethod
    @functools.cache
    def settings(cls):
        s = getattr(settings, cls.setting_name)
        if not isinstance(s, collections.abc.Mapping):
            raise TypeError(
                f"settings.{cls.setting_name} should be a dict not {type(s).__name__}"
            )
        return s

    @classmethod
    def get_formatter(cls):
        """Return the response formatter."""
        formatter_path: str = getattr(cls.settings(), "formatter", "default")

        if formatter_path.lower() == "default":
            formatter: Formatter = cls.default_formatter
        else:
            formatter: Formatter = importlib.import_module(formatter_path)
            if not callable(formatter):
                raise TypeError("Response formatter must be a callable")

        return formatter

    def is_json_response(self, response: Response) -> bool:
        """
        Check if the response is a JSON response.

        :param response: The response object.
        :return: True if the response is a JSON response, False otherwise.
        """
        return response.get("Content-Type", "").startswith("application/json")

    async def can_format(
        self, request: Request, response: Response
    ) -> bool:
        """
        Check if the response can be formatted.

        :param request: The request object.
        :param response: The response object.
        :return: True if the response can be formatted, False otherwise.
        """
        if not getattr(
            self.settings(), "enforce_format", True
        ) and not self.is_json_response(response):
            return False

        excluded_paths: List[str] = getattr(self.settings(), "exclude", [])
        request_path = "/" + str(request.url).rsplit("/", maxsplit=1)[-1]

        for path in excluded_paths:
            path_pattern = re.compile(path)
            if path_pattern.match(request_path):
                return False
        return True

    async def format(
        self, request: Request, response: Response
    ) -> Response:
        """
        Format the response.

        :param request: The request object.
        :param response: The response object.
        :return: The formatted response object.
        """
        can_format = await self.can_format(request, response)
        if not can_format:
            return response

        try:
            if asyncio.iscoroutinefunction(self.formatter):
                formatted_response = await self.formatter(response)
            else:
                formatted_response = await run_in_threadpool(self.formatter, response)
        except Exception as exc:
            log_exception(exc)
            return response
        return formatted_response

    async def pre_format(
        self, request: Request, response: Response
    ) -> Response:
        """
        Should contain logic to be executed before formatting the response.
        """
        return response

    async def post_format(
        self, request: Request, formatted_response: Response
    ) -> Response:
        """
        Should contain logic to be executed after formatting the response.
        """
        return formatted_response

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response = await self.pre_format(request, response)
        formatted_response = await self.format(request, response)
        formatted_response = await self.post_format(request, formatted_response)
        return formatted_response
