"""Simple dataclass implementation with field validation."""

import typing
from collections import defaultdict
from types import MappingProxyType
from typing_extensions import Self, Unpack

from .fields import Field, FieldInitKwargs
from .exceptions import SerializationError, FrozenInstanceError
from .serializers import Serializer


DataClassSerializer: typing.TypeAlias = typing.Callable[
    [
        "_DataClass_co",
        int,
        typing.Optional[typing.Dict[str, typing.Any]],
    ],
    typing.Any,
]
"""
Dataclass serializer type alias.

This is a callable that takes a dataclass instance and an optional depth parameter,
which specifies how deep to serialize nested dataclass instances.
"""


def dataclass_serializer(
    instance: "DataClass",
    depth: int = 0,
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> typing.Dict[str, typing.Any]:
    """
    Serialize a dataclass instance to a dictionary.

    :param instance: The dataclass instance to serialize.
    :param depth: Depth for nested serialization.
    :param context: Additional context for serialization.
    :return: A dictionary representation of the dataclass instance.
    """
    serialized_data = {}
    for key, field in instance.__data_fields__.items():
        try:
            value = field.__get__(instance, owner=type(instance))
            if depth == 0:
                serialized_data[key] = value
                continue

            if isinstance(value, DataClass):
                if depth <= 0:
                    serialized_data[key] = value
                    continue

                serialized_data[key] = dataclass_serializer(
                    value, (depth or 1) - 1, context
                )
            else:
                updated_context = {**(context or {}), "depth": depth}
                serialized_data[key] = field.serialize(
                    value,
                    fmt="python",
                    context=updated_context,
                )
        except (TypeError, ValueError) as exc:
            raise SerializationError(
                f"Failed to serialize '{type(instance).__name__}.{key}'.",
                key,
            ) from exc
    return serialized_data


def dataclass_json_serializer(
    instance: "DataClass",
    depth: int = 0,
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> typing.Dict[str, typing.Any]:
    """
    Serialize a dataclass instance to a JSON-compatible dictionary.

    :param instance: The dataclass instance to serialize.
    :param depth: Depth for nested serialization.
    :param context: Additional context for serialization.
    :return: A JSON-compatible dictionary representation of the dataclass instance.
    """
    json_ = {}
    for key, field in instance.__data_fields__.items():
        try:
            value = field.__get__(instance, owner=type(instance))
            if isinstance(value, DataClass):
                if depth <= 0:
                    json_[key] = value
                    continue

                json_[key] = dataclass_json_serializer(
                    value, depth=(depth or 1) - 1, context=context
                )
            else:
                updated_context = {**(context or {}), "depth": depth}
                json_[key] = field.serialize(
                    value,
                    fmt="json",
                    context=updated_context,
                )
        except (TypeError, ValueError) as exc:
            raise SerializationError(
                f"Failed to serialize '{type(instance).__name__}.{key}'.",
                key,
            ) from exc
    return json_


def unsupported_serializer(
    instance: "DataClass",
    depth: int = 0,
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> None:
    """Raise an error for unsupported serialization."""
    raise SerializationError(
        f"Unsupported serialization format for {type(instance).__name__}. "
        f"Supported formats are: {', '.join(instance.serializer.serializer_map.keys())}."
    )


def _unsupported_serializer_factory() -> DataClassSerializer:
    """
    Return a function that raises an error for unsupported serialization.

    To be used in defaultdict for dataclass serializer instantiation.
    :return: A function that raises a SerializationError.
    """
    return unsupported_serializer


def get_data_fields(cls: typing.Type) -> typing.Dict[str, Field]:
    if hasattr(cls, "__data_fields__"):
        return dict(cls.__data_fields__)

    fields = {}
    for key, value in cls.__dict__.items():
        if isinstance(value, Field):
            fields[key] = value
    return fields


def _sort_by_name(item: typing.Tuple[str, Field]) -> str:
    return item[1].name or item[0]


def _dataclass_repr(
    dataclass: "DataClass",
) -> str:
    """Build a string representation of the dataclass."""
    fields = dataclass.__data_fields__
    field_strs = []
    dataclass_type = type(dataclass)
    for key, field in fields.items():
        value = field.__get__(dataclass, owner=dataclass_type)
        field_strs.append(f"{key}={value}")
    return f"{dataclass_type.__name__}({', '.join(field_strs)})"


def _dataclass_str(
    dataclass: "DataClass",
) -> str:
    """Build a string representation of the dataclass."""
    fields = dataclass.__data_fields__
    field_values = {}
    dataclass_type = type(dataclass)
    for key, field in fields.items():
        value = field.__get__(dataclass, owner=dataclass_type)
        field_values[key] = value
    return field_values.__repr__()


def _dataclass_getitem(dataclass: "DataClass", key: str) -> typing.Any:
    field = type(dataclass).__data_fields__[key]
    return field.__get__(dataclass, owner=type(dataclass))


def _dataclass_setitem(dataclass: "DataClass", key: str, value: typing.Any) -> None:
    field = type(dataclass).__data_fields__[key]
    field.__set__(dataclass, value)


def _frozen_dataclass_setattr(
    dataclass: "DataClass",
    key: str,
    value: typing.Any,
) -> None:
    """Raise an error if trying to set an attribute on a frozen dataclass."""
    raise FrozenInstanceError(
        f"Cannot modify frozen field '{key}' with value: {value}"
    ) from None


def _get_slotted_dataclass_state(
    slotted_dataclass: "DataClass",
) -> typing.Tuple[typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]]:
    """Get the state of the slotted dataclass."""
    fields = slotted_dataclass.__data_fields__
    field_values = {}
    dataclass_type = type(slotted_dataclass)
    for key, field in fields.items():
        value = field.__get__(slotted_dataclass, owner=dataclass_type)
        field_values[key] = value

    attributes = {}
    pickleable_attributes = getattr(slotted_dataclass, "__slots__", [])
    for attr_name in pickleable_attributes:
        if attr_name in fields:
            continue
        if not hasattr(slotted_dataclass, attr_name):
            continue
        value = getattr(slotted_dataclass, attr_name)
        attributes[attr_name] = value
    return field_values, attributes


def _set_slotted_dataclass_state(
    slotted_dataclass: "DataClass",
    state: typing.Tuple[typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]],
) -> "DataClass":
    """Set the state of the slotted dataclass."""
    field_values, attributes = state
    slotted_dataclass._load_data(field_values)
    for key, value in attributes.items():
        if key in slotted_dataclass.__data_fields__:
            continue
        setattr(slotted_dataclass, key, value)
    return slotted_dataclass


def _build_slotted_namespace(
    original_namespace: typing.Dict[str, typing.Any],
    fields: typing.Dict[str, Field],
    additional_slots: typing.Optional[typing.Union[typing.Tuple[str], str]] = None,
) -> typing.Dict[str, typing.Any]:
    """
    Build a new namespace for a slotted dataclass.

    :param original_namespace: The original namespace of the dataclass.
    :param fields: The fields of the dataclass.
    :param additional_slots: Additional slots to include in the __slots__ attribute.
    :return: A new namespace with __slots__ and the original attributes, excluding fields.
    """
    slots = {*fields.keys()}
    if additional_slots:
        if isinstance(additional_slots, str):
            slots.add(additional_slots)
        else:
            slots.update(additional_slots)

    namespace = {}
    for key, value in original_namespace.items():
        if key == "__slots__":
            if isinstance(value, str):
                slots.add(value)
            else:
                slots.update(value)
            continue
        if key in slots:
            continue
        namespace[key] = value

    if "__getstate__" not in original_namespace:
        namespace["__getstate__"] = _get_slotted_dataclass_state
    if "__setstate__" not in original_namespace:
        namespace["__setstate__"] = _set_slotted_dataclass_state

    namespace.pop("__dict__", None)
    namespace.pop("__weakref__", None)
    namespace["__slots__"] = tuple(slots)
    return namespace


u = str


class DataClassMeta(type):
    """Metaclass for DataClass types"""

    def __new__(
        cls,
        name,
        bases,
        attrs,
        frozen: bool = False,
        slots: typing.Union[typing.Tuple[str], bool] = False,
        repr: bool = False,
        str: bool = False,
        sort: typing.Union[
            bool, typing.Callable[[typing.Tuple[str, Field]], typing.Any]
        ] = False,
        getitem: bool = False,
        setitem: bool = False,
    ):
        """
        Create a new DataClass type.

        :param name: Name of the new class.
        :param bases: Base classes for the new class.
        :param attrs: Attributes and namespace for the new class.
        :param slots: If True, use __slots__ for instance attribute storage.
            If a tuple, use as additional slots.
            If False, use __dict__ for instance attribute storage.
        :param dict_repr: Whether to use dict representation for __repr__ or to use the default.
        :param sort: If True, sort fields by name. If a callable, use as the sort key.
            If False, do not sort fields.
        :param getitem: If True, add __getitem__ method to the class.
        :param setitem: If True, add __setitem__ method to the class.
        :return: New DataClass type
        """
        fields = {}
        alias_map = {}
        for key, value in attrs.items():
            if isinstance(value, Field):
                value.post_init_validate()
                fields[key] = value
                alias_map[key] = value.alias or key

        for cls_ in bases:
            for c in cls_.mro()[:-1]:
                if hasattr(c, "__data_fields__"):
                    c = typing.cast(typing.Type["DataClass"], c)
                    fields.update(c.__data_fields__)
                    alias_map.update(c.alias_map)
                else:
                    found_fields = get_data_fields(c)
                    if not found_fields:
                        continue

                    for key, field in found_fields.items():
                        # field.post_init_validate() # Should have been done in the super class
                        fields[key] = field
                        alias_map[key] = field.alias or key

        sort = attrs.get("sort", sort)
        if sort:
            if callable(sort):
                sort_key = sort
            else:
                sort_key = _sort_by_name

            sort_key = typing.cast(
                typing.Callable[[typing.Tuple[u, Field]], u], sort_key
            )
            fields_data = list(fields.items())
            fields_data.sort(key=sort_key)
            fields = dict(fields_data)

        if repr:
            attrs["__repr__"] = _dataclass_repr
        if str:
            attrs["__str__"] = _dataclass_str
        if getitem:
            attrs["__getitem__"] = _dataclass_getitem
        if setitem:
            attrs["__setitem__"] = _dataclass_setitem

        if slots:
            # Replace the original namespace with a slotted one
            attrs = _build_slotted_namespace(
                original_namespace=attrs,
                fields=fields,
                additional_slots=slots
                if isinstance(slots, (u, tuple, list, set))
                else None,
            )
        else:
            attrs.pop("__slots__", None)

        # Make read-only to prevent accidental modification
        attrs["__data_fields__"] = MappingProxyType(fields)
        attrs["alias_map"] = MappingProxyType(alias_map)
        new_cls = super().__new__(cls, name, bases, attrs)

        if slots:
            # Bind the fields to the new class since they have been removed
            # from the original namespace and only their names are in __slots__.
            for field_name, field in fields.items():
                field.__set_name__(new_cls, field_name)
        return new_cls


class DataClass(metaclass=DataClassMeta):
    """
    Simple dataclass implementation with field validation.

    Dataclasses are defined by subclassing `DataClass` and defining fields as class attributes.
    Dataclasses enforce type validation, field requirements, and custom validation functions.
    """

    __slots__ = ("serializer",)
    __data_fields__: typing.Mapping[str, Field[typing.Any]] = {}
    alias_map: typing.Mapping[str, str] = {}
    default_serializers: typing.Mapping[str, DataClassSerializer] = {
        "python": dataclass_serializer,
        "json": dataclass_json_serializer,
    }

    def __init__(
        self,
        data: typing.Mapping[str, typing.Any],
        serializers: typing.Optional[typing.Mapping[str, DataClassSerializer]] = None,
    ) -> None:
        """
        Initialize the dataclass with raw data or keyword arguments.

        :param data: Raw data to initialize the dataclass with.
        :param serializers: Optional mapping of serializers to use for serialization.
        """
        all_serializers = {
            **self.default_serializers,
            **(serializers or {}),
        }
        self.serializer = Serializer(
            defaultdict(
                _unsupported_serializer_factory,
                all_serializers,
            )
        )
        self._load_data(data)

    def _load_data(self, data: typing.Mapping[str, typing.Any]) -> Self:
        """
        Load raw data into the dataclass instance.

        :param data: Mapping of raw data to initialize the dataclass instance with.
        :return: This same instance with the raw data loaded.
        """
        for key, field in type(self).__data_fields__.items():
            data_key = type(self).alias_map[key]
            if data_key not in data:
                value = field.get_default()
            else:
                value = data[data_key]

            field.__set__(self, value)
        return self

    def __init_subclass__(cls) -> None:
        """Ensure that subclasses define fields."""
        if len(cls.__data_fields__) == 0:
            raise TypeError("Subclasses must define fields")
        return

    @typing.overload
    def serialize(
        self,
        *,
        fmt: typing.Literal["python", "json"],
        depth: int = 0,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Dict[str, typing.Any]: ...

    @typing.overload
    def serialize(
        self,
        *,
        fmt: str,
        depth: int = 0,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Any: ...

    @typing.overload
    def serialize(
        self,
        *,
        fmt: str = "python",
        depth: int = 0,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Any: ...

    def serialize(
        self,
        *,
        fmt: str = "python",
        depth: int = 0,
        context: typing.Optional[typing.Dict[str, typing.Any]] = None,
    ) -> typing.Any:
        """Return a serialized representation of the dataclass."""
        try:
            return self.serializer(fmt, self, depth, context)
        except (TypeError, ValueError) as exc:
            raise SerializationError(
                f"Failed to serialize '{type(self).__name__}'.", exc
            ) from exc


_DataClass = typing.TypeVar("_DataClass", bound=DataClass)
_DataClass_co = typing.TypeVar("_DataClass_co", bound=DataClass, covariant=True)


def _get_slots_and_attributes(
    cls: typing.Type[_DataClass_co],
) -> typing.Tuple[typing.Set[str], typing.Dict[str, typing.Any]]:
    """
    Inspect and extract slots and necessary attributes required to build a slotted namespace.
    for a DataClass.

    :param cls: The DataClass type to inspect.
    :return: A tuple containing a set of slot names and a dictionary of attributes.
    """
    slots = {
        *cls.__data_fields__.keys(),
    }
    attributes = {}
    for key, value in cls.__dict__.items():
        if key == "__slots__":
            if isinstance(value, str):
                slots.add(value)
            else:
                slots.update(value)
            continue
        if key in slots:
            continue
        attributes[key] = value

    if "__getstate__" not in attributes:
        attributes["__getstate__"] = _get_slotted_dataclass_state
    if "__setstate__" not in attributes:
        attributes["__setstate__"] = _set_slotted_dataclass_state

    attributes.pop("__dict__", None)
    attributes.pop("__weakref__", None)
    return slots, attributes


def _build_slotted_namespace_for_cls(
    cls: typing.Type[_DataClass_co],
    additional_slots: typing.Optional[typing.Union[typing.Tuple[str], str]] = None,
) -> typing.Dict[str, typing.Any]:
    """
    Build a namespace for a DataClass that uses __slots__ for instance attribute storage.

    :param cls: The DataClass type to build the namespace for.
    :return: A dictionary containing the namespace for the DataClass.
    """
    slots, attributes = _get_slots_and_attributes(cls)
    if additional_slots:
        if isinstance(additional_slots, str):
            slots.add(additional_slots)
        else:
            slots.update(additional_slots)

    namespace = {"__slots__": tuple(slots), **attributes}
    return namespace


@typing.overload
def slotted(
    cls: None = None,
    *,
    slots: typing.Optional[typing.Union[typing.Tuple[str], str]] = None,
) -> typing.Callable[
    [typing.Type[_DataClass_co]],
    typing.Type[_DataClass_co],
]: ...


@typing.overload
def slotted(
    cls: typing.Type[_DataClass_co],
    *,
    slots: typing.Optional[typing.Union[typing.Tuple[str], str]] = None,
) -> typing.Type[_DataClass_co]: ...


def slotted(
    cls: typing.Optional[typing.Type[_DataClass_co]] = None,
    *,
    slots: typing.Optional[typing.Union[typing.Tuple[str], str]] = None,
) -> typing.Union[
    typing.Callable[
        [typing.Type[_DataClass_co]],
        typing.Type[_DataClass_co],
    ],
    typing.Type[_DataClass_co],
]:
    """
    Decorator that modifies a DataClass to use __slots__ for instance attribute storage
    instead of __dict__, improving memory efficiency.

    :param cls: The DataClass type to modify.
    :return: The modified DataClass with __slots__.
    """
    if cls is None:
        return lambda cls: slotted(cls, slots=slots)

    if not issubclass(cls, DataClass):
        raise TypeError("use_slots can only be applied to DataClass types.")

    namespace = _build_slotted_namespace_for_cls(cls, additional_slots=slots)
    new_cls = type(
        cls.__name__,
        (cls,),
        namespace,
    )
    new_cls = typing.cast(typing.Type[_DataClass_co], new_cls)
    return new_cls


###############
# NestedField #
###############


def nested_dataclass_json_serializer(
    instance: _DataClass_co,
    field: Field[_DataClass_co],
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> typing.Dict[str, typing.Any]:
    """Serialize a nested dataclass instance to a dictionary."""
    depth = context.get("depth", 0) if context else 0
    return dataclass_json_serializer(instance, depth=depth, context=context)


def nested_dataclass_python_serializer(
    instance: _DataClass_co,
    field: Field[_DataClass_co],
    context: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> typing.Dict[str, typing.Any]:
    """Serialize a nested dataclass instance to a dictionary."""
    depth = context.get("depth", 0) if context else 0
    return dataclass_serializer(instance, depth=depth, context=context)


class NestedField(Field[_DataClass]):
    """Nested DataClass field."""

    default_serializers = {
        "python": nested_dataclass_python_serializer,
        "json": nested_dataclass_json_serializer,
    }

    def __init__(
        self,
        dataclass: typing.Type[_DataClass],
        **kwargs: Unpack[FieldInitKwargs[_DataClass]],
    ) -> None:
        super().__init__(dataclass, **kwargs)

    def post_init_validate(self):
        super().post_init_validate()
        self.field_type = typing.cast(typing.Type[_DataClass], self.field_type)
        if not issubclass(self.field_type, DataClass):
            raise TypeError(
                f"{self.field_type} must be a subclass of {DataClass.__name__}."
            )


__all__ = [
    "DataClass",
    "NestedField",
    "slotted",
]
