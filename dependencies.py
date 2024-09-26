import importlib
import typing
import functools


class DependencyRequired(Exception):
    """Raised when a required dependency is missing."""

    def __init__(self, missing_dependencies):
        message = "The following dependencies are required but missing:\n"
        for name, url_or_package in missing_dependencies:
            if url_or_package.startswith("http"):
                message += f"{name}: Visit {url_or_package} for installation.\n"
            else:
                message += (
                    f"{name}: Install by running `pip install {url_or_package}`.\n"
                )
        super().__init__(message)
        self.missing_dependencies = missing_dependencies


def required_deps(dependencies: typing.Dict[str, str]):
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
        raise DependencyRequired(missing)


def depends_on(dependencies: typing.Dict[str, str]):
    """
    Function decorator.
    
    Checks if the dependencies or packages required by a module are installed on calling the function.
    
    :param dependencies: A dictionary of required dependencies where the key is the package name,
    and the value is the package URL or package name.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            required_deps(dependencies)
            return func(*args, **kwargs)

        return wrapper

    return decorator
