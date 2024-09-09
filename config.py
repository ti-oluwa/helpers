import functools
from typing import Any, Dict
from django.conf import settings as django_settings

from .utils.misc import merge_dicts


def _make_proxy_getter(module, settings: Any):
    def proxy_getter(name: str) -> Any:
        try:
            value = getattr(settings, name)
        except AttributeError:
            value = getattr(settings, name.upper())
        return value

    if hasattr(module, "__getattr__"):
        return functools.wraps(module.__getattr__)(proxy_getter)
    return proxy_getter


def make_proxy(module, settings):
    """
    Makes settings accessible through the module
    """
    module.__getattr__ = _make_proxy_getter(module, settings)
    return module


DEFAULT_SETTINGS = {
    "WEBSOCKETS": {
        "CHANNELS": {
            "AUTH": {
                "API_KEY": {
                    "header": "WS_X_API_KEY",
                    "model": "rest_framework_api_key.models.APIKey",
                },
                "TOKEN": {
                    "header": "WS_X_AUTH_TOKEN",
                    "model": "rest_framework.authtoken.models.Token",
                },
            },
            "MIDDLEWARE": [
                "channels.security.websocket.AllowedHostsOriginValidator",
            ],
        }
    },
    "MAINTENANCE_MODE": {"status": "off", "message": "default:minimal_dark"},
    "RESPONSE_FORMATTER": {"formatter": "default", "exclude": [r"/admin*"]},
}


class ValueStoreProxy:
    """
    Proxy for accessing the values in a value store or dictionary as attributes
    """

    def __init__(self, valuestore: Dict[str, Any]) -> None:
        self.valuestore = valuestore

    def __getattr__(self, name: str) -> Any:
        try:
            return self.valuestore[name]
        except KeyError as exc:
            raise AttributeError(exc)


class _Settings(ValueStoreProxy):
    """Lazy settings loader"""

    __instance = None

    def __init__(self, setting_name: str) -> None:
        if self.__instance:
            raise ValueError("Settings already loaded")

        self.__instance = self
        settings: Dict[str, Any] = merge_dicts(
            DEFAULT_SETTINGS, getattr(django_settings, setting_name, {})
        )
        return super().__init__(settings)


settings = _Settings("HELPERS_SETTINGS")
"""`helpers` module's settings"""
