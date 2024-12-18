import collections.abc
from typing import Dict, Mapping, Union, Any
import fastapi
from starlette.middleware.base import BaseHTTPMiddleware
from helpers.fastapi.exceptions import ImproperlyConfigured

from helpers.fastapi.config import settings
from helpers.logging import log_exception
from helpers import RESOURCES_PATH
from helpers.dependencies import depends_on


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle application maintenance mode.
    The middleware will return a 503 Service Unavailable response with the maintenance message.

    #### Ensure to place this middleware at the top of `MIDDLEWARE` settings.

    Middleware settings:

    - `MAINTENANCE_MODE.status`: Set as "ON" or "OFF", True or False, to enable or disable maintenance mode.
    - `MAINTENANCE_MODE.message`: The message to display in maintenance mode. Can be a path to a template file or a string.

    There are default maintenance message templates available:

    - `default:minimal`: Minimal and clean. Light-themed
    - `default:minimal_dark`: Dark-themed minimal
    - `default:techno`: Techno-themed
    - `default:jazz`: Playful jazz-themed

    In settings.py:

    ```python
    MAINTENANCE_MODE = {
        "status": True,
        "message": "default:techno"
    }
    ```
    """

    templates_dir = RESOURCES_PATH / "templates/maintenance"
    defaults_prefix = "default:"
    setting_name = "MAINTENANCE_MODE"

    @depends_on({"aiofiles": "aiofiles"})
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        s = getattr(settings, type(self).setting_name)
        if not isinstance(s, collections.abc.Mapping):
            raise TypeError(
                f"settings.{self.setting_name} should be a dict not {type(s).__name__}"
            )

        self.settings: Mapping[str, Any] = s

    def _maintenance_mode_on(self) -> bool:
        """Check if the application is in maintenance mode."""
        status = str(self.settings.get("status", "off"))
        return status.lower() in ["on", "true"]

    async def get_message(self) -> Union[str, bytes]:
        """Return the maintenance message."""
        msg = self.settings.get("message", "default:minimal")

        if not isinstance(msg, str):
            raise ImproperlyConfigured(f"{self.setting_name}.message must be a string")

        if msg.lower().startswith(self.defaults_prefix.lower()):
            slice_start = len(type(self).defaults_prefix)
            template_name = msg[slice_start:]
            msg = await self.get_default_template(template_name)

        return msg or "Service Unavailable"

    async def get_default_template(self, name: str) -> Union[bytes, None]:
        """Get the default maintenance template content."""
        import aiofiles

        template_path = type(self).templates_dir / f"{name.lower()}.html"
        try:
            if template_path.exists():
                async with aiofiles.open(template_path, "rb") as file:
                    return await file.read()
        except Exception as exc:
            log_exception(exc)
        return None

    async def get_response_content(self) -> Union[str, bytes]:
        """Returns the response content."""
        return await self.get_message()

    async def get_response_headers(self) -> Dict[str, Any]:
        """Returns the response headers."""
        return {
            "Content-Type": "text/html",
        }

    async def dispatch(self, request: fastapi.Request, call_next) -> fastapi.Response:
        """Process the request."""
        if self._maintenance_mode_on():
            content = await self.get_response_content()
            headers = await self.get_response_headers()
            return fastapi.Response(content, status_code=503, headers=headers)

        response = await call_next(request)
        return response
