import typing
import attrs
import cattrs

_AI = typing.TypeVar("_AI", bound=attrs.AttrsInstance)


def cast_on_set_factory(converter: cattrs.Converter):
    def _cast_on_set(instance, attribute, value):
        """
        Cast the value to the attribute type if it exists and handle nested attrs classes.
        Uses the provided converter for nested attrs classes.
        """
        if attrs.has(attribute.type):
            # If the attribute is an attrs class, recursively structure it using the provided converter
            return converter.structure(value, attribute.type)
        
        if getattr(attribute, "converter", None):
            value = attribute.converter(value)
        
        try:
            # Otherwise, cast it to the declared type
            return attribute.type(value) if attribute.type else value
        except (TypeError, ValueError):
            # If not possible, return value as is
            return value

    return _cast_on_set


def structure_with_casting_factory(converter: cattrs.Converter):
    def _structure_with_casting(
        data: typing.Dict[str, typing.Any],
        cls: typing.Type[_AI],
    ) -> _AI:
        """
        Structuring hook for cattrs converters that casts values to the declared type.

        Supports nested attrs-based classes and uses the provided converter.
        """
        cast_on_set = cast_on_set_factory(converter)
        
        # Explicitly fetch the value using attr.name to avoid mismatch issues
        return cls(
            **{
                attr.name: cast_on_set(None, attr, data.get(attr.name))
                for attr in cls.__attrs_attrs__
            }
        )

    return _structure_with_casting


def unstructure_with_casting_factory(converter: cattrs.Converter):
    def _unstructure_with_casting(instance):
        """
        Unstructures the attrs-based class instance and casts values to their declared types.

        Handles both base and subclass instances, as well as nested attrs-based classes.
        Non-attrs types are unstructured using the provided converter.
        """
        if not attrs.has(instance.__class__):
            return converter.unstructure(instance)

        data = {}
        for attr in instance.__attrs_attrs__:
            value = getattr(instance, attr.name)

            if attrs.has(attr.type):
                # If the attribute is an attrs class, recursively unstructure it using the provided converter
                data[attr.name] = _unstructure_with_casting(value)
            else:
                # Delegate non-attrs types to the converter (useful for lists, dicts, or custom types)
                data[attr.name] = converter.unstructure(value)

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
