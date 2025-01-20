"""Simple dataclass implementation with field validation."""

import json
import typing
from types import MappingProxyType

try:
    from typing_extensions import Self
except ImportError:
    from typing import Self

from .fields import Field, FieldMeta, FieldInitKwargs, FieldError, _Field, empty, Unpack


class DataClassMeta(FieldMeta):
    """Metaclass for dataclass types."""

    def __new__(meta_cls, name, bases, attrs):
        fields = {}
        for key, value in attrs.items():
            if isinstance(value, Field):
                fields[key] = value

        # Make fields read-only to prevent accidental modification
        attrs["__fields__"] = MappingProxyType(fields)
        return super().__new__(meta_cls, name, bases, attrs)


class DataClass(Field[Self], metaclass=DataClassMeta):
    """
    Base class for simple dataclasses with field validation.

    Dataclasses are defined by subclassing `DataClass` and defining fields as class attributes.
    Dataclasses enforce type validation, field requirements, and custom validation functions.

    Dataclasses can also be nested (like fields) within other dataclasses to create structured data.
    """

    __valuestore__ = "__data__"

    def __init__(
        self,
        raw: typing.Optional[typing.Dict[str, typing.Any]] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ) -> None:
        """
        Initialize the dataclass with raw data or keyword arguments.

        :param raw: A dictionary of raw data to initialize the dataclass with.
        :param kwargs: Additional keyword arguments to initialize the dataclass with.
        """
        super().__init__(type_=type(self), **kwargs)
        if raw:
            self._load_raw(raw)
        return
    
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        # Remove raw data from stored initialization args and kwargs, as this data is used
        # to create a new instance during a deepcopy. Including the raw data will mostly likely set-off
        # a chain of deepcopies for nested/structured dataclass, leading to a very slow
        # data load time.
        instance._init_args = ()
        instance._init_kwargs.pop("raw", None)
        return instance

    def _load_raw(self, raw: typing.Dict[str, typing.Any]):
        """
        Load raw data into the dataclass instance, initializing fields with the provided values.

        :param raw: A dictionary of raw data to initialize the dataclass instance with.
        :return: This same instance with the raw data loaded unto the fields.
            i.e id(field) == id(field._load_raw(value))
        """
        if not isinstance(raw, dict):
            raise TypeError("Raw data must be a dictionary.")

        for key, field in type(self).__fields__.items():
            field_name = field.get_name()
            value = raw.get(field_name, field.get_default())
            self._set_field_value(key, value, field)
        return self

    def _set_field_value(self, key: str, value: typing.Any, field: _Field) -> None:
        """Set and validate a field value for initialization."""
        if value is empty:
            if field.required:
                raise FieldError(
                    f"'{type(self).__name__}.{key}' is required but was not provided."
                )
        else:
            setattr(self, key, value)
        return

    def __init_subclass__(cls) -> None:
        """Ensure that subclasses define fields."""
        if not getattr(cls, "__fields__", None):
            raise TypeError("Subclasses must define fields")
        return

    def __repr__(self) -> str:
        return f"{type(self).__name__}<{self.__values__}>"

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        """Return a dictionary representation of the dataclass."""
        result = {}
        for key, field in type(self).__fields__.items():
            value = getattr(self, key)
            if isinstance(value, DataClass):
                value = value.to_dict()

            result[field.get_name()] = value
        return result

    # Leave instance kwarg for uniformity/compatibility with Field.json method.
    # However, DataClass classes do not need to access the instance as they contain
    # the data required for serialization.
    def to_json(self, instance: "_DataClass" = None) -> typing.Dict[str, typing.Any]:
        """Return a JSON serializable representation of the dataclass."""
        json_data = {}
        for key, field in type(self).__fields__.items():
            # If field is a DataClass, we cannot use the field present
            # in cls.__fields__, as cls.__fields__ contains all fields initially captured
            # during class instantiation. This class-specific fields are used
            # to create a copy for the instance when the field's value is set on the instance.
            # Therefore, it is shared across all instances of this class and will mostlikely not have any values set.
            # Instead, we get the copy of the field specific to the instance.
            # The instance's copy will contain the necessary values set on the field (if any)
            if isinstance(field, DataClass):
                field = getattr(self, key)

            value = field.to_json(self)
            field_name = field.get_name()
            try:
                json_data[field_name] = json.loads(json.dumps(value))
            except (TypeError, ValueError) as exc:
                raise FieldError(
                    f"Failed to serialize '{type(self).__name__}.{field_name}' to JSON. "
                    "Consider implementing a custom json method or using a supported type."
                ) from exc
        return json_data

    def __getitem__(self, key: str) -> typing.Any:
        if key not in type(self).__fields__:
            raise FieldError(f"Field '{key}' does not exist in {type(self).__name__}")
        return getattr(self, key)
    

_DataClass = typing.TypeVar("_DataClass", bound=DataClass, covariant=True)

__all__ = ["DataClass", "_DataClass"]
