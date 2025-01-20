"""Simple dataclass implementation with field validation."""

import typing
from types import MappingProxyType
from typing_extensions import Self, Unpack

from .fields import (
    FieldBase,
    Field,
    FieldMeta,
    FieldInitKwargs,
)
from .exceptions import FieldError


class DataClassMeta(FieldMeta):
    """Metaclass for dataclass types."""

    def __new__(cls, name, bases, attrs):
        data_cls = super().__new__(cls, name, bases, attrs)
        alias_map = {}
        for key, field in data_cls.__fields__.items():
            alias_map[key] = field.alias or key

        # Make read-only to prevent accidental modification
        data_cls.alias_map = MappingProxyType(alias_map)
        return data_cls


class DataClass(Field[Self], metaclass=DataClassMeta):
    """
    Base class for simple dataclasses with field validation.

    Dataclasses are defined by subclassing `DataClass` and defining fields as class attributes.
    Dataclasses enforce type validation, field requirements, and custom validation functions.

    Dataclasses can also be nested (like fields) within other dataclasses to create structured data.
    """

    sort_fields = True

    @typing.overload
    def __init__(self, data: typing.Mapping[str, typing.Any]) -> None: ...

    @typing.overload
    def __init__(self, **kwargs: Unpack[FieldInitKwargs[Self]]) -> None: ...

    def __init__(
        self,
        data: typing.Optional[typing.Mapping[str, typing.Any]] = None,
        **kwargs: Unpack[FieldInitKwargs[Self]],
    ) -> None:
        """
        Initialize the dataclass with raw data or keyword arguments.

        :param data: A mapping of raw data to initialize the dataclass with.
        :param lazy: If True, the raw data is stored in the instance and fields are not initialized immediately.
            Using Dataclass as fields themselves can be expensive especially during initialization (Loading data).
            This option allows for lazy loading of the data into the fields of the Dataclass only when accessed.
            This reduces the time taken to load data into the Dataclass instance. However, caveats include:
            - Raw data is stored in the instance, which may increase memory usage.
            - Validation of the data is not done until the data is accessed. Hence, errors will only be raised on attribute access.
            - In the advent that the lazy Dataclass has nested non-lazy Dataclass fields, the nested fields will be
                remaining uninitialized until accessed, meaning full data loading for such fields will be done on access,
                which may be expensive.
            - Lazy loading is not recommended for multi-level nested Dataclasses, as it may lead to unexpected behavior.

            On the other hand, if False, the raw data is loaded into the fields immediately during initialization.
            Validation of the data is done immediately, and errors are raised if the data does not meet the field requirements.
            Of course, this is at the expense of time (may be slower).

        :param kwargs: Additional keyword arguments to initialize the dataclass with.
        """
<<<<<<< HEAD
        kwargs.setdefault("lazy", True)
        super().__init__(type_=type(self), **kwargs)

        if data is not None:
            self.load_data(data)
=======
        super().__init__(type_=type(self), **kwargs)
        if raw:
            self._load_raw(raw)
>>>>>>> a03e649 (Update to django modules)
        return

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        # Remove raw data from stored initialization args and kwargs, as this data is used
        # to create a new instance during a deepcopy. Including the raw data will mostly likely set-off
        # a chain of deepcopies for nested/structured dataclasses, leading to a very slow
        # data load time.
        instance._init_args = ()
        instance._init_kwargs.pop("data", None)
        return instance

    def load_data(self, data: typing.Mapping[str, typing.Any]) -> Self:
        """
        Load raw data into the dataclass instance, initializing fields with the provided values.

        :param data: Mapping of raw data to initialize the dataclass instance with.
        :return: This same instance with the raw data loaded unto the fields.
            i.e id(field) == id(field.load_data(value))
        """
        for key, field in type(self).__fields__.items():
            data_key = type(self).alias_map[key]
            if data_key not in data:
                value = field.get_default()
            else:
                value = data[data_key]

            field.__set__(self, value)
        return self

    def __init_subclass__(cls) -> None:
        """Ensure that subclasses define fields."""
        if not cls.__fields__:
            raise TypeError("Subclasses must define fields")
        return

    def __repr__(self) -> str:
        return f"{type(self).__name__}<{self._values}>"

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        """Return a dictionary representation of the dataclass."""
        # Set pending values to ensure that all fields are validated
        pending_validation = dict(self._pending)
        if pending_validation:
            fields = dict(type(self).__fields__)
            for key, value in pending_validation.items():
                field = fields[key]
                field.setvalue(self, value, validate=True)

        # Get the (validated) values of the fields
        validated = dict(self._values)
        # Sort the fields such that DataClass fields come first
        dataclasses_first = dict(
            sorted(validated.items(), key=lambda x: not isinstance(x[1], DataClass))
        )
        # Recursively convert DataClass fields to dictionaries
        for key, value in dataclasses_first.items():
            if isinstance(value, DataClass):
                validated[key] = value.to_dict()
                continue
            # If we reach here, there is no more values that are DataClass instances
            break
        return validated

    def to_json(
        self, instance: typing.Optional[FieldBase] = None
    ) -> typing.Dict[str, typing.Any]:
        """Return a JSON serializable representation of the dataclass."""
        json_ = {}
        fields = dict(type(self).__fields__)
        for key, field in fields.items():
            # If field is a DataClass, we cannot use the field present
            # in cls.__fields__, as cls.__fields__ contains all fields initially captured
            # during class instantiation. These class-specific fields are used
            # to create a copy for the instance when the field's value is set on the instance.
            # Therefore, it is shared across all instances of this class and will mostlikely not have any values set.
            # Instead, we get the copy of the field specific to the instance.
            # The instance's copy will contain the necessary values set on the field (if any)
            if isinstance(field, DataClass):
                if instance is None:
                    field = field.__get__(self, owner=type(self))
                else:
                    field = self.__get__(instance, owner=type(instance))

            try:
                json_[key] = field.to_json(self)
            except (TypeError, ValueError) as exc:
                raise FieldError(
                    f"Failed to serialize '{type(self).__name__}.{key}'.",
                    key,
                ) from exc
        return json_

    def __getitem__(self, key: str) -> typing.Any:
        field: FieldBase = type(self).__fields__[key]
        return field.__get__(self, owner=type(self))

    def __setitem__(self, key: str, value: typing.Any) -> None:
        field: FieldBase = type(self).__fields__[key]
        field.__set__(self, value)


_DataClass_co = typing.TypeVar("_DataClass_co", bound=DataClass, covariant=True)

__all__ = ["DataClass", "_DataClass_co"]
