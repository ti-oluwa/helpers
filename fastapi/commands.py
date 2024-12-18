import argparse
import enum
import inspect
import string
import typing
import functools
import asyncio
import itertools
import sys
import fastapi.exceptions
from typing import Any, Dict, Optional, Callable, Union

from helpers.generics.utils.functions import get_function_params_details, NOT_SET
from helpers.generics.utils.misc import is_generic_type
from helpers.logging import log_exception


_Registry = Dict[str, Dict[str, Any]]


def _wrap_handler(
    handler: Callable[..., None], handler_details: Dict[str, Dict[str, Any]]
) -> Callable[..., None]:
    """
    Wraps command handlers to only accept a argument parser

    :param handler: Command handler
    :param handler_details: Command handler details
    """
    args = handler_details["args"]
    kwargs = handler_details["kwargs"]
    variadic = handler_details["variadic"]
    variadic_args = None
    variadic_kwargs = None
    variadic_args_name = None
    variadic_kwargs_name = None
    if variadic:
        variadic_args: Dict = handler_details["variadic"].get("args", {})
        variadic_kwargs: Dict = handler_details["variadic"].get("kwargs", {})
        variadic_args_name = variadic_args.get("name", None)
        variadic_kwargs_name = variadic_kwargs.get("name", None)

    def _add_expected_args_and_kwargs_to_parse(
        parser: argparse.ArgumentParser,
    ) -> Any:
        for arg in itertools.chain(args.values(), kwargs.values()):
            choices = None
            arg_kind = arg["kind"]
            arg_type = arg["type"]
            if is_generic_type(arg_type):
                arg_type = None

            if inspect.isclass(arg_type) and issubclass(arg_type, enum.Enum):
                choices = [e.value for e in arg_type]

            arg_name = arg["name"]
            arg_default = arg["default"]
            arg_description = arg.get("description", "")
            names = [
                f"-{arg_name}",
            ]

            action = "store"
            if arg_type is bool:
                action = "store_true"
                arg_kind = "KEYWORD_ONLY"
                if arg_default is None:
                    arg_default = False

            if arg_kind == "POSITIONAL_OR_KEYWORD":
                names.append(f"--{arg_name}")
            elif arg_kind == "KEYWORD_ONLY":
                names = [
                    f"--{arg_name}",
                ]

            action = "store"
            if arg_type is bool:
                action = "store_true"

            parser.add_argument(
                *names,
                type=arg_type,
                action=action,
                metavar=arg_name,
                default=arg_default,
                choices=choices,
                required=arg_default is NOT_SET,
                help=arg_description,
            )

        # Handle variadic arguments (*args)
        if variadic_args:
            parser.add_argument(
                f"-{variadic_args_name}",
                nargs="*",
                type=variadic_args.get("type", list),
                default=[],
                metavar=variadic_args_name,
                help="Positional variadic arguments",
            )

        # Handle variadic keyword arguments (**kwargs)
        if variadic_kwargs:
            parser.add_argument(
                f"-{variadic_kwargs_name}",
                nargs="*",
                default=[],
                metavar="KEY=VALUE",
                help="Extra keyword arguments (key=value pairs)",
            )
        return parser

    def wrapper(parser: argparse.ArgumentParser) -> Any:
        parser = _add_expected_args_and_kwargs_to_parse(parser)
        parsed = parser.parse_args()
        params = {**vars(parsed)}
        # Exclude the command name from the params
        params.pop("command", None)

        # Handle variadic keyword arguments set (**kwargs) as a dictionary
        args = []
        kwargs = params

        # Prepare the handler's parameters
        if variadic_args:
            args = params.pop(variadic_args_name, [])

        if variadic_kwargs:
            for pair in params.pop(variadic_kwargs_name, []):
                if "=" in pair:
                    key, value = pair.split("=", maxsplit=1)
                    kwargs[key] = value

        if asyncio.iscoroutinefunction(handler):
            return asyncio.run(handler(*args, **kwargs))
        return handler(*args, **kwargs)

    return functools.wraps(handler)(wrapper)


def make_registrar(
    registry: _Registry,
) -> Callable[
    ...,
    Union[Callable[..., None], Callable[[Callable[..., None]], Callable[..., None]]],
]:
    """
    Factory function.

    Makes a new registrar for the specified command registry.
    The created registrar can add/register new commands to the
    registry.

    The created registrar can be used as a decorator or regular function.

    ```python
    MY_REGISTRY: _Registry = {}

    register = make_registrar(MY_REGISTRY)

    @register(name="flush")
    def clear_db(*args, **kwargs):
        # Do something
        ...

    print(MY_REGISTRY)
    ```
    """

    def _registrar(
        handler: Optional[Callable[..., None]] = None, name: Optional[str] = None
    ) -> Union[
        Callable[..., None], Callable[[Callable[..., None]], Callable[..., None]]
    ]:
        """
        Registers a new command in the registry

        :param handler: Command handler
        :param name: Command name
        :return: Command handler or decorator
        """
        nonlocal registry

        def decorator(handler: Callable[..., None]) -> Callable[..., None]:
            nonlocal name

            if not callable(handler):
                raise TypeError(
                    f"handler should be a callable of type {Callable[..., None]}"
                )

            name = name or handler.__name__
            if name in registry:  # Can't register a command twice
                return handler

            handler_details = get_function_params_details(handler)
            handler = _wrap_handler(handler, handler_details)
            registry[name] = {
                "handler": handler,
                "description": handler.__doc__,
                **handler_details,
            }
            return handler

        if handler is not None:
            return decorator(handler)
        return decorator

    return _registrar


BASE_REGISTRY: _Registry = {}

register = make_registrar(BASE_REGISTRY)
"""Registers a new command in the base commands registry"""


COMMAND_USAGE_TEMPLATE = string.Template(
    """
$command:  
    description: $description
    options: $options
"""
)

COMMAND_OPTIONS_TEMPLATE = string.Template(
    """     
        $name ($type) - $description
"""
)


def _generate_command_usage(command: str, details: Dict[str, Any]) -> str:
    """
    Generates usage string for the given command

    :param command: Command name
    :param details: Command details
    :return: Usage string
    """
    options = ""
    args = details["args"]
    kwargs = details["kwargs"]
    variadic = details["variadic"]
    for arg in itertools.chain(
        args.values(),
        kwargs.values(),
        variadic.values(),
    ):
        arg_name = arg["name"]
        arg_type = arg["type"]
        description: str = arg.get("description", "").strip()
        default = arg["default"]

        if default is not NOT_SET:
            description += f" Defaults to {default}"

        options += COMMAND_OPTIONS_TEMPLATE.substitute(
            name=arg_name,
            type=repr(arg_type),
            description=description,
        )
    return COMMAND_USAGE_TEMPLATE.substitute(
        command=command,
        description=details.get("description"),
        options=options,
    )


def _generate_usage_from_registry(registry: _Registry) -> str:
    """
    Generates usage string from the given command registry

    :param registry: A dictionary of commands and their handlers
    :return: Usage string
    """
    usage = "Available commands include:\n"
    for command, details in registry.items():
        usage += _generate_command_usage(command, details)
    return usage


def capture_input(
    prompt: str, validators: typing.Optional[typing.List[typing.Callable]] = None
) -> typing.Any:
    """
    Capture input from the user.

    :param prompt: The prompt to display to the user.
    :param validators: A list of callables that will validate the input.
    :return: The validated input.
    """
    validators = validators or []
    while True:
        value = input(prompt)
        try:
            for validator in validators:
                validator(value)
        except ValueError as exc:
            sys.stderr.write(f"Invalid value: {exc}\n")
            sys.stderr.flush()
        except fastapi.exceptions.ValidationException as exc:
            sys.stderr.write(f"Invalid value: {"\n".join(exc.errors())}\n")
            sys.stderr.flush()
        else:
            return value


def parse_command(
    parser: argparse.ArgumentParser,
    registry: _Registry,
) -> None:
    """
    Parses command based on the given command registry

    :param parser: argparse.ArgumentParser instance
    :param registry: A dictionary of commands and their handlers
    """
    parser.add_argument(
        "command",
        type=str,
        help="The name of the command to execute",
        action="store",
        metavar="command",
        choices=list(registry.keys()),
    )

    args = parser.parse_known_args()[0]
    command_name = args.command
    handler = registry[command_name]["handler"]
    return handler(parser)


def main(commands_registry: typing.Optional[_Registry] = None) -> None:
    """
    Main function to execute the command line interface

    :param commands_registry: A dictionary of commands and their handlers
    :type commands_registry: A dictionary of commands and their handlers
    """
    parser = argparse.ArgumentParser(description="Execute a command")
    registry = {**BASE_REGISTRY, **(commands_registry or {})}
    parser.usage = _generate_usage_from_registry(registry)
    try:
        parse_command(parser, registry)
    except Exception as exc:
        log_exception(exc)
        raise


__all__ = [
    "make_registrar",
    "register",
    "parse_command",
    "capture_input",
    "main",
]
