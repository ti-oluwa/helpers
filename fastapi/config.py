import os
from typing import Any

import collections.abc
import importlib
from types import ModuleType

from helpers.generics.utils.misc import merge_dicts
from helpers.generics.types import MappingProxy
from . import default_settings


SETTINGS_ENV_VARIABLE = "FAST_API_SETTINGS_MODULE"


def _settings_from_module(module: ModuleType):
    settings = {}
    for attr in dir(module):
        if not attr.isupper():
            continue
        settings[attr] = getattr(module, attr)
    return settings


def load_settings(settings_module: str):
    """Load settings from a module"""
    module = importlib.import_module(settings_module)
    return _settings_from_module(module)


class Settings:
    """Application Settings"""

    def __init__(self):
        self.__dict__["_store"] = None

    @property
    def configured(self):
        return self._store is not None and isinstance(
            self._store, collections.abc.Mapping
        )

    def __setattr__(self, name: Any, value: Any):
        raise RuntimeError(f"{type(self).__name__} cannot be modified")

    def __getattr__(self, name: str) -> Any:
        if not self.configured:
            raise RuntimeError(
                f"{type(self).__name__} not configured. "
                f"Run `configure()` to attribute before access"
            )
        try:
            return self._store[name]
        except KeyError as exc:
            raise AttributeError(exc) from exc

    def __getitem__(self, name: Any) -> Any:
        return getattr(self, name)

    def __repr__(self):
        return f"{type(self).__name__}({repr(self._wrapped)})"

    def configure(self, **options) -> None:
        if self.configured:
            return

        defined = load_settings(os.environ[SETTINGS_ENV_VARIABLE])
        defaults = _settings_from_module(default_settings)
        aggregate = merge_dicts(defined, defaults)

        for key, value in options:
            if not key.isupper():
                raise ValueError(
                    "Options for settings should be provided in upper case."
                )
            aggregate[key] = value

        self.__dict__["_store"] = MappingProxy(aggregate, recursive=True)


settings = Settings()
