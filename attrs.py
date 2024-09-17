import typing
import attrs
import cattrs
from typing import (
    get_origin,
    get_args,
    TypeVar,
    Callable,
    Dict,
    Type,
    Any,
)
from .utils.misc import is_generic_type, is_mapping_type, is_iterable_type

_AI = TypeVar("_AI", bound=attrs.AttrsInstance)


def structure_to_generic_type(
    value: Any, attr_type: Type[Any], converter: cattrs.Converter
) -> Any:
    """
    Recursively handle generic types (List, Dict, Union, Optional, etc.) during structuring.

    :param value: The value to structure.
    :param attr_type: The type to structure the value to.
    :param converter: The cattrs Converter instance to use.
    :return: The structured value.
    """
    origin = get_origin(attr_type)
    args = get_args(attr_type)

    if origin is None:
        return value

    if origin is typing.Union:
        # Handle Union[T1, T2, ...] or Optional[T] (which is Union[T, None])
        if value is None and type(None) in args:
            return None

        for arg in args:
            try:
                return (
                    converter.structure(value, arg)
                    if not is_generic_type(arg)
                    else structure_to_generic_type(value, arg, converter)
                )
            except (TypeError, ValueError):
                continue
        return value  # Return original value if no valid cast

    if is_mapping_type(origin) and len(args) == 2:
        # Handle Mapping[K, V] (like Dict[K, V])
        _map = {}
        for k, v in value.items():
            _map_key = (
                converter.structure(k, args[0])
                if not is_generic_type(args[0])
                else structure_to_generic_type(k, args[0], converter)
            )
            _map_value = (
                converter.structure(v, args[1])
                if not is_generic_type(args[1])
                else structure_to_generic_type(v, args[1], converter)
            )
            _map[_map_key] = _map_value

        return origin(_map)

    if is_iterable_type(origin) and len(args) == 1:
        # Handle Iterable[T] (like List[T], Set[T], etc.)
        return origin(
            converter.structure(v, args[0])
            if not is_generic_type(args[0])
            else structure_to_generic_type(v, args[0], converter)
            for v in value
        )

    # Fallback for other generic types
    try:
        return origin(value)
    except (TypeError, ValueError):
        return value


def cast_on_set_factory(
    converter: cattrs.Converter,
) -> Callable[[Any, attrs.Attribute, Any], Any]:
    """
    Factory function to create a casting function for attrs-based attributes.

    :param converter: The cattrs Converter instance to use.
    :return: A function that casts attribute values.
    """

    def _cast_on_set(instance: Any, attribute: attrs.Attribute, value: Any) -> Any:
        attr_type = attribute.type
        if attr_type is None:
            return value

        if attrs.has(attr_type):
            return converter.structure(value, attr_type)
        elif is_generic_type(attr_type):
            return structure_to_generic_type(value, attr_type, converter)
        else:
            try:
                return attr_type(value)
            except (TypeError, ValueError):
                return value

    return _cast_on_set


def structure_with_casting_factory(
    converter: cattrs.Converter,
) -> Callable[[Dict[str, Any], Type[_AI]], _AI]:
    """
    Factory function to create a structuring function that casts values to declared types.

    :param converter: The cattrs Converter instance to use.
    :return: A function that structures data into an attrs-based class.
    """
    cast_on_set = cast_on_set_factory(converter)

    def _structure_with_casting(
        data: Dict[str, Any],
        cls: Type[_AI],
    ) -> _AI:
        """
        Structuring hook for cattrs converters that casts values to the declared type.

        :param data: The data to structure.
        :param cls: The attrs-based class to structure the data into.
        :return: An instance of the attrs-based class.
        """
        return cls(
            **{
                attr.name: cast_on_set(None, attr, data.get(attr.name))
                for attr in cls.__attrs_attrs__
            }
        )

    return _structure_with_casting


def unstructure_as_generic_type(
    value: Any, attr_type: Type[Any], converter: cattrs.Converter
) -> Any:
    """
    Recursively handle unstructuring of generic types (List, Dict, Union, Optional, etc.)
    using cattrs.Converter and applying the unstructure_as argument when appropriate.

    :param value: The value to unstructure.
    :param attr_type: The type to unstructure the value to.
    :param converter: The cattrs Converter instance to use.
    :return: The unstructured value.
    """
    origin = get_origin(attr_type)
    args = get_args(attr_type)

    if origin is None:
        return value

    if origin is typing.Union:
        # Handle Union[T1, T2, ...] or Optional[T] (which is Union[T, None])
        if value is None and type(None) in args:
            return None

        for arg in args:
            try:
                return (
                    converter.unstructure(value, unstructure_as=arg)
                    if not is_generic_type(arg)
                    else unstructure_as_generic_type(value, arg, converter)
                )
            except (TypeError, ValueError):
                continue
        return value  # Return original value if no valid cast

    if is_mapping_type(origin) and len(args) == 2:
        # Handle Mapping[K, V] (like Dict[K, V])
        _map = {}
        for k, v in value.items():
            _map_key = (
                converter.unstructure(k, unstructure_as=args[0])
                if not is_generic_type(args[0])
                else unstructure_as_generic_type(k, args[0], converter)
            )
            _map_value = (
                converter.unstructure(v, unstructure_as=args[1])
                if not is_generic_type(args[1])
                else unstructure_as_generic_type(v, args[1], converter)
            )
            _map[_map_key] = _map_value

        return origin(_map)

    if is_iterable_type(origin) and len(args) == 1:
        # Handle Iterable[T] (like List[T], Set[T], etc.)
        return origin(
            converter.unstructure(v, unstructure_as=args[0])
            if not is_generic_type(args[0])
            else unstructure_as_generic_type(v, args[0], converter)
            for v in value
        )

    # Fallback for other generic types
    try:
        return converter.unstructure(value, unstructure_as=origin)
    except (TypeError, ValueError):
        return value


def unstructure_with_casting_factory(
    converter: cattrs.Converter,
) -> Callable[[Any], Dict[str, Any]]:
    """
    Factory function to create an unstructuring function that casts values to declared types.

    :param converter: The cattrs Converter instance to use.
    :return: A function that unstructures an attrs-based class instance into a dictionary.
    """

    def _unstructure_with_casting(instance: Any) -> Dict[str, Any]:
        """
        Unstructures the attrs-based class instance and casts values to their declared types.

        :param instance: The attrs-based class instance to unstructure.
        :return: A dictionary representation of the instance.
        """
        if not attrs.has(instance.__class__):
            # Fallback to converter's default unstructuring for non-attrs classes
            return converter.unstructure(instance)

        data = {}
        for attr in instance.__attrs_attrs__:
            value = getattr(instance, attr.name)
            attr_type = attr.type

            if attr_type is None:
                data[attr.name] = value
            elif is_generic_type(attr_type):
                data[attr.name] = unstructure_as_generic_type(
                    value, attr_type, converter
                )
            else:
                try:
                    data[attr.name] = attr_type(value)
                except (TypeError, ValueError):
                    data[attr.name] = value

        return data

    return _unstructure_with_casting


def type_cast(
    converter: cattrs.Converter,
    cls: typing.Optional[typing.Type[_AI]] = None,
) -> typing.Union[
    typing.Callable[[typing.Type[_AI]], typing.Type[_AI]], typing.Type[_AI]
]:
    """
    Decorator.

    Registers structure and unstructure hooks for attrs-based classes on the
    provided cattrs converter instance, casting values to their declared types
    on structure and unstructure. Raises an error if the class is not an attrs-based class.

    :param converter: The cattrs converter instance to register hooks on
    :param cls: The class to register the hooks for (optional, if provided, will register hooks immediately)
    :return: The class with the hooks registered or a decorator function
    """
    if cls is None:
        return lambda cls: type_cast(converter, cls)

    # Ensure that the class is an attrs-based class
    if not attrs.has(cls):
        raise TypeError(
            f"{cls.__name__} is not an attrs-based class. Type casting is only supported for attrs classes."
        )

    # Pass the specific converter to both structure and unstructure hooks for attrs-based classes
    converter.register_structure_hook(cls, structure_with_casting_factory(converter))
    converter.register_unstructure_hook(
        cls, unstructure_with_casting_factory(converter)
    )

    return cls
