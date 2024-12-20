import copy
from inspect import isclass
import collections.abc
from io import BytesIO
from typing import (
    Iterator,
    Union,
    Callable,
    Any,
    TypeVar,
    Dict,
    Type,
    List,
    Iterable,
    AsyncIterator,
    AsyncIterable,
    Optional,
    Tuple,
)
import base64
from itertools import islice

from .choice import ExtendedEnum


def has_method(obj: Any, method_name: str) -> bool:
    """Check if an object or type has a specific method."""
    return callable(getattr(obj, method_name, None))


def type_implements_iter(tp: Type[Any], /) -> bool:
    """Check if the type has an __iter__ method (like lists, sets, etc.)."""
    return has_method(tp, "__iter__")


def is_mapping_type(tp: Type[Any], /) -> bool:
    """Check if a given type is a mapping (like dict)."""
    return isinstance(tp, type) and issubclass(tp, collections.abc.Mapping)


def is_iterable_type(
    tp: Type[Any], /, *, exclude: Optional[Tuple[Type[Any]]] = None
) -> bool:
    """
    Check if a given type is an iterable.

    :param tp: The type to check.
    :param exclude: A tuple of types to return False for, even if they are iterable types.
    """
    is_iter_type = isinstance(tp, type) and issubclass(tp, collections.abc.Iterable)
    if not is_iter_type:
        return False

    if exclude:
        for _tp in exclude:
            if not is_iterable_type(_tp):
                raise ValueError(f"{_tp} is not an iterable type.")

        is_iter_type = is_iter_type and not issubclass(tp, tuple(exclude))
    return is_iter_type


def is_iterable(obj: Any) -> bool:
    """Check if an object is an iterable."""
    return isinstance(obj, collections.abc.Iterable)


def is_generic_type(tp: Type[Any]) -> bool:
    """Check if a type is a generic type like List[str], Dict[str, int], etc."""
    return hasattr(tp, "__origin__")


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


# Left for compatibility where already in use
def merge_dicts(
    dict1: Dict,
    dict2: Dict,
    /,
    *,
    copy: Optional[Callable] = copy.copy,
):
    """Merges two (nested) dictionaries."""
    return merge_mappings(dict1, dict2, copy=copy)


_Mapping = TypeVar("_Mapping", bound=collections.abc.Mapping)

def merge_mappings(
    mapping1: _Mapping,
    mapping2: _Mapping,
    /,
    *,
    copy: Optional[Callable] = copy.copy,
) -> _Mapping:
    # If either mapping is empty, return the other
    if not mapping2:
        return copy(mapping1) if callable(copy) else mapping1
    if not mapping1:
        return copy(mapping2) if callable(copy) else mapping2

    if not (
        isinstance(mapping1, collections.abc.Mapping)
        or isinstance(mapping2, collections.abc.Mapping)
    ):
        raise TypeError("Both arguments must be dictionaries")

    merged = (
        copy(mapping1) if callable(copy) else mapping1
    )  # Start with (a copy of) mapping1
    reference = (
        copy(mapping2) if callable(copy) else mapping2
    )  # Tak mapping2 as a reference for update
    for key, value in reference.items():
        if key in merged:
            if isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge mappings
                merged[key] = merge_dicts(merged[key], value, copy=None)
            continue
        else:
            # If the key is not in mapping1 or the value is not a dictionary, override or add the value
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


T = TypeVar("T")


def batched(i: Union[Iterator[T], Iterable[T]], batch_size: int):
    """
    Create batches of size n from the given iterable.

    :param iterable: The iterable to split into batches.
    :param batch_size: The batch size.
    :yield: Batches of the iterable as lists.
    """
    iterator = iter(i)
    while batch := list(islice(iterator, batch_size)):
        yield batch


async def async_batched(
    async_iter: Union[AsyncIterable[T], AsyncIterator[T]], batch_size: int
) -> AsyncIterator[List[T]]:
    """
    Create batches of size batch_size from the given async iterable.

    :param async_iter: The async iterable to split into batches.
    :param batch_size: The batch size.
    :yield: Batches of the async iterable as lists.
    """
    batch = []
    async for item in async_iter:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch


__all__ = [
    "is_iterable_type",
    "is_iterable",
    "is_generic_type",
    "is_mapping_type",
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
    "batched",
    "async_batched",
]
