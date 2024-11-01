import importlib
import typing
import functools
import warnings

try:
    from typing_extensions import ParamSpec
except ImportError:
    from typing import ParamSpec

_P = ParamSpec("_P")
_R = typing.TypeVar("_R")


class DependencyRequired(Exception):
    """Raised when a required dependency is missing."""

    def __init__(self, *missing_dependencies: typing.Tuple[str, str]):
        message = "The following dependencies are required but missing:\n"
        for name, url_or_package in missing_dependencies:
            if not url_or_package:
                message += f"{name}: Install the package"
            else:
                if url_or_package.startswith("http"):
                    message += f"{name}: Visit {url_or_package} for installation.\n"
                else:
                    message += (
                        f"{name}: Install by running `pip install {url_or_package}`.\n"
                    )
        super().__init__(message)
        self.missing_dependencies = missing_dependencies


def deps_required(dependencies: typing.Dict[str, str]):
    """
    Helper function to check if the dependencies or packages required by a module are installed.

    :param dependencies: A dictionary of required dependencies where the key is the package name,
    and the value is the package URL or package name.
    :raises DependencyRequired: If any of the required dependencies are missing.
    """
    missing = []
    for name, url_or_package in dict(dependencies).items():
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append((name, url_or_package))

    if missing:
        raise DependencyRequired(*missing)


def deps_warning(dependencies: typing.Dict[str, str]):
    """
    Helper function to check and raise a warning if the dependencies or packages required by a module are not installed.

    :param dependencies: A dictionary of required dependencies where the key is the package name,
    and the value is the package URL or package name.
    """
    try:
        deps_required(dependencies)
    except DependencyRequired as exc:
        warnings.warn(str(exc), UserWarning, stacklevel=2)
    return


def depends_on(dependencies: typing.Dict[str, str], warning: bool = False):
    """
    Function decorator.

    Checks if the dependencies or packages required by a module are installed on execting the function.

    :param dependencies: A dictionary of required dependencies where the key is the package name,
    and the value is the package URL or package name.
    :param warning: If True, a warning is raised instead of an exception.
    """

    def decorator(func: typing.Callable[_P, _R]) -> typing.Callable[_P, _R]:
        @functools.wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            if warning:
                deps_warning(dependencies)
            else:
                deps_required(dependencies)
            return func(*args, **kwargs)

        return wrapper

    return decorator
