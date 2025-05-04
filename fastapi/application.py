import typing
import fastapi

from .middleware.core import apply_middleware
from .dependencies import Dependency
from .config import settings
from helpers.generics.utils.module_loading import import_string


SetupName: typing.TypeAlias = str
"""Setup name"""
SetupFunc = typing.Callable[[fastapi.FastAPI], fastapi.FastAPI]
"""Setup function - takes a (FastAPI) application and performs some post initialization setup on it"""

SETUPS: typing.Dict[SetupName, SetupFunc] = {
    "apply_middleware": apply_middleware,  # default middleware setup
}
"""Registered application setups"""


def app_setup(
    setup: typing.Optional[SetupFunc] = None, name: typing.Optional[SetupName] = None
) -> SetupFunc | typing.Callable[[SetupFunc], SetupFunc]:
    """
    Installs a new FastAPI application setup function.

    Can also be used as decorator

    :param setup: setup function
    :param name: setup name
    """
    global SETUPS

    def decorator(setup: SetupFunc) -> SetupFunc:
        nonlocal name

        if not callable(setup):
            raise TypeError(f"`setup` should be a callable of type {SetupFunc}")

        name = name or setup.__name__
        if name in SETUPS:  # Can't install a setup twice
            return setup

        SETUPS[name] = setup
        return setup

    if setup is not None:
        return decorator(setup)
    return decorator


def default_dependencies():
    """
    Yield default dependencies for FastAPI application defined in settings.

    :return: default dependencies
    """
    for dep_path in settings.DEFAULT_DEPENDENCIES:
        if not isinstance(dep_path, str):
            raise ValueError(
                "Entry in 'DEFAULT_DEPENDENCIES' must be a string path to the dependency"
            )
        yield Dependency(import_string(dep_path))


def exception_handlers():
    """
    Yield exception handlers for FastAPI application defined in settings.
    """
    for exc, handler_path in settings.EXCEPTION_HANDLERS.items():
        if not issubclass(exc, Exception):
            if isinstance(exc, str):
                exc = import_string(exc)
            else:
                raise ValueError("Key in 'EXCEPTION_HANDLERS' must be an exception class")

        handler = import_string(handler_path)
        yield exc, handler


@app_setup
def add_exception_handlers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    """
    Add exception handlers to the FastAPI application instance.

    :param app: FastAPI application instance
    :return: FastAPI application instance
    """
    for exc, handler in exception_handlers():
        app.add_exception_handler(exc, handler)
    return app


def get_application(**configs) -> fastapi.FastAPI:
    """
    Get a FastAPI application instance with the provided configurations.

    :param configs: configurations for FastAPI application
    :return: FastAPI application instance
    """
    dependencies = list(configs.get("dependencies", []))
    for dep in default_dependencies():
        if dep in dependencies:
            continue
        dependencies.append(dep)

    configs["dependencies"] = dependencies
    app = fastapi.FastAPI(**configs)
    return setup_application(app)


def setup_application(app: fastapi.FastAPI) -> fastapi.FastAPI:
    """
    Apply all registered setups to the FastAPI application instance.

    :param app: FastAPI application instance
    :return: FastAPI application instance
    """
    for func in SETUPS.values():
        _app = func(app)
        if _app is not None:
            app = _app
    return app
