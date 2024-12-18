import inspect
from typing import Any, Callable, Dict


class _NOT_SET:
    """Sentinel object to indicate that a value was not provided."""
    def __bool__(self):
        return False
    
    def __repr__(self):
        return "NOT_SET"

NOT_SET = _NOT_SET()

def get_function_params_details(func: Callable) -> Dict[str, Any]:
    """
    Returns details of the function's expected args and kwargs, with
    information about their types, defaults, and kind.

    :param func: The function to analyze.
    :return: A dictionary with details of the function's args and kwargs.

    Example:
    ```python

    def my_func(a: int, b: str = "default", *args, **kwargs):
        pass

    print(get_function_params_details(my_func))
    >>> {
        "args": {
            "a": {
                "name": "a",
                "type": int,
                "default": NOT_SET,
                "kind": "POSITIONAL_ONLY",
            },
        },
        "kwargs": {
            "b": {
                "name": "b",
                "type": str,
                "default": "default",
                "kind": "POSITIONAL_OR_KEYWORD",
            },
        },
        "variadic": {
            "args": {
                "name": "args",
                "type": None,
                "default": None,
                "kind": "VAR_POSITIONAL",
            },
            "kwargs": {
                "name": "kwargs",
                "type": None,
                "default": None,
                "kind": "VAR_KEYWORD",
            },
        },
    }
    """
    details = {"args": {}, "kwargs": {}, "variadic": {}}

    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        param_info = {
            "name": name,
            "type": param.annotation
            if param.annotation is not inspect.Parameter.empty
            else NOT_SET,
            "default": param.default
            if param.default is not inspect.Parameter.empty
            else NOT_SET,
            "kind": param.kind.name,
        }

        # Classify based on kind
        if param.kind == inspect.Parameter.POSITIONAL_ONLY:
            details["args"][name] = param_info
        elif param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            if param.default is inspect.Parameter.empty:
                details["args"][name] = param_info
            else:
                details["kwargs"][name] = param_info
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            details["kwargs"][name] = param_info
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            details["variadic"]["args"] = param_info
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            details["variadic"]["kwargs"] = param_info

    return details


__all__ = [
    "get_function_params_details",
]
