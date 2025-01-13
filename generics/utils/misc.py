import copy
import sys
import inspect
import collections.abc
from typing import (
    Iterator,
    TypeGuard,
    Union,
    Callable,
    Any,
    TypeVar,
    Dict,
    Type,
    List,
    Set,
    Iterable,
    AsyncIterator,
    AsyncIterable,
    Optional,
    Tuple,
    Sequence,
)
import base64
import functools
from itertools import islice
from typing_extensions import Buffer

from .choice import ExtendedEnum


def get_memory_size(obj: Any, seen: Optional[Set[int]] = None) -> float:
    """Recursively calculate the total memory size of an object and its references."""
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(
            get_memory_size(k, seen) + get_memory_size(v, seen) for k, v in obj.items()
        )
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(get_memory_size(i, seen) for i in obj)
    return size


def has_method(obj: Any, method_name: str) -> bool:
    """Check if an object or type has a specific method."""
    return callable(getattr(obj, method_name, None))


def type_implements_iter(tp: Type[Any], /) -> bool:
    """Check if the type has an __iter__ method (like lists, sets, etc.)."""
    return has_method(tp, "__iter__")


def is_mapping(obj: Any) -> TypeGuard[collections.abc.Mapping]:
    """Check if an object is a mapping (like dict)."""
    return isinstance(obj, collections.abc.Mapping)


def is_mapping_type(tp: Type[Any], /) -> TypeGuard[Type[collections.abc.Mapping]]:
    """Check if a given type is a mapping (like dict)."""
    return inspect.isclass(type) and issubclass(tp, collections.abc.Mapping)


def is_iterable_type(
    tp: Type[Any], /, *, exclude: Optional[Tuple[Type[Any], ...]] = None
) -> TypeGuard[Type[collections.abc.Iterable]]:
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


def is_iterable(obj: Any, *, exclude: Optional[Tuple[Type[Any], ...]] = None) -> TypeGuard[collections.abc.Iterable]:
    """Check if an object is an iterable."""
    return is_iterable_type(type(obj), exclude=exclude)


def is_generic_type(tp: Any) -> bool:
    """Check if a type is a generic type like List[str], Dict[str, int], etc."""
    return hasattr(tp, "__origin__")


def is_exception_class(exc) -> TypeGuard[Type[BaseException]]:
    return inspect.isclass(exc) and issubclass(exc, BaseException)


def str_to_base64(s: str, encoding: str = "utf-8") -> str:
    b = s.encode(encoding=encoding)
    return bytes_to_base64(b)


def bytes_to_base64(b: Union[Buffer, bytes]) -> str:
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
    parts = path.split(delimiter)
    value = data
    for key in parts:
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
    parts = path.split(delimiter)
    value = obj
    for key in parts:
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


_Mapping = TypeVar("_Mapping", bound=collections.abc.MutableMapping)


def merge_mappings(
    *mappings: _Mapping,
    merge_nested: bool = True,
    merger: Optional[Callable[[_Mapping, _Mapping], _Mapping]] = None,
    copier: Optional[Callable[[_Mapping], _Mapping]] = copy.copy,
) -> _Mapping:
    """
    Merges two or more mappings into a single mapping.
    Starting from the back, each mapping is merged into the penultimate mapping.

    For example, merging `{"a": 1, "b": 2}`, `{"b": 3, "c": 4}`, `{"c": 5, "d": 6}`
    would result in `{"a": 1, "b": 3, "c": 5, "d": 6}`.

    :param mappings: The mappings to merge.
    :param merge_nested: Whether to merge nested mappings. If set to `False`, nested mappings
        will be overridden by the source mapping. Defaults to `True`.
    :param merger: The function to use for merging nested mappings. If not provided, nested mappings
        will be merged recursively using this function. Defaults to `None`.
        An important not is that the merger should only use generic mapping properties when merging
        E.g. merger's should use `value = mapping[key]`, instead of `mapping.get(key)`.
        Except you are sure that the mapping all support the `get` method.
    :param copier: The function to use for copying mappings.
        Should return a new mapping with the same keys and values as the input mapping.
        Defaults to `copy.copy`. Set to `None` to avoid copying, Although this is not recommended,
        as modifications to the returned mapping may affect the input mappings and vice versa.
    :return: A new mapping containing all the keys and values from the provided mappings.

    Example Usage:
    ```python
    import collections

    merged = merge_mappings(
        {"a": 1, "b": 2},
        {"b": 3, "c": 4},
        {"c": 5, "d": {"e": 6}},
        {"d": {"e": 7, "f": 8}},
        merge_nested=True,
        merger=collections.ChainMap,
    )

    print(merged)
    # Output: {'a': 1, 'b': 3, 'c': 5, 'd': ChainMap({'e': 6}, {'e': 7, 'f': 8})}
    ```
    """
    if not mappings:
        raise ValueError("At least one mapping must be provided")

    if not all(isinstance(mapping, collections.abc.Mapping) for mapping in mappings):
        raise TypeError("All arguments must be mappings")

    copier = copier or (
        lambda x: x
    )  # Just return the input mapping if no copier is provided
    if len(mappings) == 1:
        return copier(mappings[0])

    merger = merger or _default_mappings_merger

    # Start from the back and merge each mapping into the penultimate mapping
    target = copier(mappings[-2])
    source = mappings[-1]
    for key, source_value in source.items():
        if merge_nested is False or key not in target:
            target[key] = source_value
            continue
        # From here on merging of nested mappings is allowed and the
        # source key has been confirmed to be in the target mapping

        #  If the source and target values are both mappings, recursively merge
        #  the source value into the target value
        if isinstance(target[key], collections.abc.Mapping) and isinstance(
            source_value, collections.abc.Mapping
        ):
            target[key] = merger(target[key], source_value) # type: ignore
        else:
            # Otherwise, just override the target value with the source value
            target[key] = source_value

    return merge_mappings(
        *mappings[:-2],
        target,
        merge_nested=merge_nested,
        merger=merger,
        copier=copier,
    )


_default_mappings_merger = functools.partial(merge_mappings, copier=None)


# Left for compatibility where already in use
def merge_dicts(
    *dicts: Dict,
    **kwargs,
):
    """
    Merges two or more dictionaries into a single dictionary.

    Deprecated: Use `merge_mappings` instead.
    """
    return merge_mappings(*dicts, **kwargs)


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


def comma_separated_to_int_float(value: str) -> Union[str, int, float]:
    """Convert a comma-separated string into a single integer or float by concatenating the numbers."""
    if not value:
        return 0

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


def shift(i: Sequence[T], /, *, step: int = 1) -> Sequence[T]:
    """
    Shifts the elements of an iterable by the given step

    Use a negative step to shift the elements in the backwards direction.
    """
    return [*i[-step:], *i[:-step]]


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
    "get_value_by_traversal_path",
    "get_attr_by_traversal_path",
    "merge_dicts",
    "merge_mappings",
    "merge_enums",
    "get_dict_diff",
    "underscore_dict_keys",
    "python_type_to_html_input_type",
    "batched",
    "async_batched",
    "shift",
]
