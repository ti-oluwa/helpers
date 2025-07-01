import os
import typing
import collections.abc
import importlib
from types import ModuleType

from helpers.generics.utils.misc import merge_mappings
from helpers.types import MappingProxy
from . import default_settings


SETTINGS_ENV_VARIABLE = "FAST_API_SETTINGS_MODULE"


def _settings_from_module(module: ModuleType) -> typing.Dict[str, typing.Any]:
    settings = {}
    for attr in dir(module):
        if not attr.isupper():
            continue
        settings[attr] = getattr(module, attr)
    return settings


def load_settings(settings_module: str) -> typing.Dict[str, typing.Any]:
    """Load settings from a module"""
    module = importlib.import_module(settings_module)
    return _settings_from_module(module)


class Settings:
    """
    Application Settings.

    Loads settings from a module and provide a read-only interface to access them.

    By default, settings are loaded from the module specified in the `FAST_API_SETTINGS_MODULE` environment variable.
    and is merged with the default settings provided in the `default_settings` module.

    Example:
    ```python
    import fastapi
    from helpers.fastapi.config import settings

    async def lifespan(app: fastapi.FastAPI) -> None:
        try:
            settings.configure(DEBUG=True)
            # do other pre-startup setup
            yield
        finally:
            pass

    app = fastapi.FastAPI(lifespan=lifespan, ...)

    print(settings.DEBUG) # True
    ```
    """

    def __init__(self):
        self.__dict__["_store"] = None

    @property
    def configured(self) -> bool:
        return self._store is not None and isinstance(
            self._store, collections.abc.Mapping
        )

    def __setattr__(self, name: typing.Any, value: typing.Any):
        raise RuntimeError(f"{self.__name__} cannot be modified")

    def __getattr__(self, name: str) -> typing.Any:
        if not self.configured:
            raise RuntimeError(
                f"{self.__name__} not configured. "
                f"Run `configure(...)` before attribute access"
            )
        try:
            return self._store[name]
        except KeyError as exc:
            raise AttributeError(exc) from exc

    def __getitem__(self, name: typing.Any) -> typing.Any:
        return getattr(self, name)

    def configure(self, **options) -> None:
        if self.configured:
            return

        user_defined_settings = load_settings(os.environ[SETTINGS_ENV_VARIABLE])
        default_setting = _settings_from_module(default_settings)
        aggregate_settings = merge_mappings(
            default_setting, user_defined_settings, merge_nested=True
        )

        for key, value in options:
            if not key.isupper():
                raise ValueError(
                    "Options for settings should be provided in upper case."
                )
            aggregate_settings[key] = value

        self.__dict__["_store"] = MappingProxy(aggregate_settings, recursive=True)


settings = Settings()
