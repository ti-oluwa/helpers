from inspect import isclass
import collections.abc
from io import BytesIO
from typing import Union, Callable, Any, TypeVar, Dict, Type
import base64

from .choice import ExtendedEnum


def has_method(obj: Any, method_name: str) -> bool:
    """Check if an object or type has a specific method."""
    return callable(getattr(obj, method_name, None))


def type_implements_iter(tp: Type[Any]) -> bool:
    """Check if the type has an __iter__ method (like lists, sets, etc.)."""
    return has_method(tp, "__iter__")


def is_mapping_type(tp: Type[Any]) -> bool:
    """Check if a given type is a mapping (like dict)."""
    return isinstance(tp, type) and issubclass(tp, collections.abc.Mapping)


def is_iterable_type(tp: Type[Any]) -> bool:
    """Check if a given type is an iterable (like list, set, tuple), but not a string."""
    # Exclude str from being considered an iterable for this use case
    return (
        isinstance(tp, type)
        and issubclass(tp, collections.abc.Iterable)
        and not issubclass(tp, (str, bytes))
    )


def is_generic_type(tp: Type[Any]) -> bool:
    """Check if a type is a generic type like List[str], Dict[str, int], etc."""
    return hasattr(tp, "__origin__") or tp is Any


def is_exception_class(exc):
    return isclass(exc) and issubclass(exc, BaseException)


def str_to_base64(s: str, encoding: str = "utf-8") -> str:
    b = s.encode(encoding=encoding)
    return bytes_to_base64(b)


def bytes_to_base64(b: Union[BytesIO, bytes]) -> str:
    """Convert bytes to a base64 encoded string."""
    return base64.b64encode(b).decode()


def str_is_base64(s: str, encoding: str = "utf-8") -> bool:
    try:
        if not isinstance(s, str):
            return False
        # Encode string to bytes and then decode
        b = s.encode(encoding=encoding)
        decoded = base64.b64decode(b, validate=True)
        # Encode back to base64 to check if it matches original
        return base64.b64encode(decoded).decode() == s.strip()
    except Exception:
        return False


def bytes_is_base64(b: bytes) -> bool:
    try:
        if not isinstance(b, bytes):
            return False
        decoded = base64.b64decode(b, validate=True)
        # Encode back to base64 to check if it matches original
        return base64.b64encode(decoded) == b.strip()
    except Exception:
        return False


Composable = TypeVar("Composable", bound=Callable[..., Any])


def compose(*functions: Composable) -> Composable:
    """
    Compose multiple functions into a single function.

    :param functions: The functions to be composed.
    :return: A composed function.
    """

    def apply(function: Composable, *args, **kwargs):
        return function(*args, **kwargs)

    def composed(*args, **kwargs):
        # initial = apply(functions[0], *args, **kwargs)
        # return functools.reduce(apply, functions, initial)
        ...

    return composed


def get_value_by_traversal_path(
    data: Dict[str, Any], path: str, delimiter: str = "."
) -> Union[Any, None]:
    """
    Get the value from a nested dictionary using a traversal path.

    :param data: The dictionary to traverse.
    :param path: The traversal path to the value.
    :param delimiter: The delimiter used in the traversal path.
    :return: The value at the end of the traversal path.
    """
    path = path.split(delimiter)
    value = data
    for key in path:
        value = value.get(key, None)
        if value is None:
            return None
    return value


def get_attr_by_traversal_path(
    obj: Any, path: str, delimiter: str = "."
) -> Union[Any, None]:
    """
    Get the attribute from an object using a traversal path.

    :param obj: The object to traverse.
    :param path: The traversal path to the attribute.
    :param delimiter: The delimiter used in the traversal path.
    :return: The attribute at the end of the traversal path.
    """
    path = path.split(delimiter)
    value = obj
    for key in path:
        value = getattr(value, key, None)
        if value is None:
            return None
    return value


def get_dict_diff(dict1: Dict, dict2: Dict) -> Dict:
    """
    Get the changes between two dictionaries

    The changes in the values of the dictionaries are returned as a new dictionary
    """
    diff_dict = {}
    for key, value in dict1.items():
        if isinstance(value, dict):
            diff = get_dict_diff(value, dict2.get(key, {}))
            if diff:
                diff_dict[key] = diff
            continue

        dict2_value = dict2.get(key)
        if value == dict2_value:
            continue
        diff_dict[key] = dict2_value
    return diff_dict


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Merges two (nested) dictionaries."""
    # If either dict is empty, return the other
    if not dict2:
        return dict1.copy()
    if not dict1:
        return dict2.copy()

    if not (isinstance(dict1, dict) or isinstance(dict2, dict)):
        raise TypeError("Both arguments must be dictionaries")

    merged = dict1.copy()  # Start with a copy of dict1
    for key, value in dict2.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # Recursively merge dictionaries
            merged[key] = merge_dicts(merged[key], value)
        else:
            # If the key is not in dict1 or the value is not a dictionary, override or add the value
            merged[key] = value
    return merged


def merge_enums(name, *enums) -> ExtendedEnum:
    """
    Merges multiple Enums into a single Enum.

    :param name: The name of the new Enum.
    :param enums: The Enums to merge.
    :return: A new Enum containing all the members from the provided Enums.
    """
    members = {}
    for enum in enums:
        for member in enum:
            if member.name in members:
                raise ValueError(f"Duplicate enum name found: {member.name}")
            members[member.name] = member.value

    return ExtendedEnum(name, members)


def underscore_dict_keys(_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Replaces all hyphens in the dictionary keys with underscores"""
    return {key.replace("-", "_"): value for key, value in _dict.items()}


def comma_separated_to_int_float(value: str) -> Union[int, float]:
    """Convert a comma-separated string into a single integer or float by concatenating the numbers."""
    if not isinstance(value, str):
        return value
    if not value:
        return value

    try:
        stripped_value = "".join(value.split(","))
        if "." in stripped_value:
            return float(stripped_value)
        return int(stripped_value)
    except ValueError:
        return value


def python_type_to_html_input_type(py_type: type) -> str:
    """
    Maps a Python type to the appropriate HTML input type.

    Args:
        py_type (type): The Python type to be mapped.

    Returns:
        str: The corresponding HTML input type as a string.

    - `NoneType`: mapped to "text"
    - `str`: mapped to "text"
    - `int`: mapped to "number"
    - `float`: mapped to "number"
    - `bool`: mapped to "checkbox"
    - `list` or `tuple`: mapped to "text" (assuming comma-separated values)
    - `dict`: mapped to "text"
    - `bytes`: mapped to "file"
    - Default type: mapped to "text"
    """
    if py_type is type(None):
        return "text"
    if issubclass(py_type, str):
        return "text"
    if issubclass(py_type, int):
        return "number"
    if issubclass(py_type, float):
        return "number"
    if issubclass(py_type, bool):
        return "checkbox"
    if issubclass(py_type, (list, tuple)):
        return "text"  # Assuming you may want a comma-separated list
    if issubclass(py_type, dict):
        return "text"  # Handling complex types can vary
    if issubclass(py_type, bytes):
        return "file"

    # Default case for unsupported types
    return "text"


__all__ = [
    "is_exception_class",
    "str_to_base64",
    "bytes_to_base64",
    "str_is_base64",
    "bytes_is_base64",
    "compose",
    "get_value_by_traversal_path",
    "get_attr_by_traversal_path",
    "merge_dicts",
    "merge_enums",
    "get_dict_diff",
    "underscore_dict_keys",
    "python_type_to_html_input_type",
]
