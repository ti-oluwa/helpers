"""Data fields"""

from __future__ import annotations
from types import MappingProxyType, NoneType
import uuid
import decimal
import datetime
import functools
import typing
import json
import base64
import io
import copy
import ipaddress
from urllib3.util import Url, parse_url
from typing_extensions import Unpack, Self

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo

from helpers.generics.utils.misc import is_generic_type, is_iterable_type, is_iterable
from helpers.dependencies import depends_on
from helpers.generics.utils.datetime import iso_parse, parse_duration
from helpers.generics.utils.misc import merge_mappings
from . import validators
from .exceptions import FieldError
from .utils import iexact


_T = typing.TypeVar("_T", covariant=True)
_R = typing.TypeVar("_R")
_V = typing.TypeVar("_V")


class empty:
    """Class to represent missing/empty values."""

    def __bool__(self):
        return False

    def __init_subclass__(cls):
        raise TypeError("empty cannot be subclassed.")

    def __new__(cls):
        raise TypeError("empty cannot be instantiated.")


class undefined:
    """Class to represent an undefined type."""

    def __init_subclass__(cls):
        raise TypeError("undefined cannot be subclassed.")

    def __new__(cls):
        raise TypeError("undefined cannot be instantiated.")


_FieldValidator: typing.TypeAlias = typing.Callable[
    [
        typing.Union[typing.Any, _T],
        typing.Optional[typing.Union[typing.Any, "FieldBase[_T]"]],
        typing.Optional[typing.Union[typing.Any, "FieldBase[_V]"]],
    ],
    None,
]
"""Field validator type alias. 
Args: value, field_instance, instance
"""
DefaultFactory = typing.Callable[[], typing.Union[_T, typing.Any]]
"""Type alias for default value factories."""


def _is_type(o: typing.Any) -> bool:
    """Check if an object is a type."""
    if is_iterable(o):
        return all(isinstance(obj, type) for obj in o)
    return isinstance(o, type)


def _prep_values(
    values: typing.Iterable[typing.Any],
) -> typing.Union[typing.Set[typing.Any], typing.Tuple[typing.Any, ...]]:
    """Prepare values for comparison."""
    if not is_iterable(values, exclude=(str, bytes)):
        raise TypeError("values must be an iterable.")

    try:
        return frozenset(values)
    except TypeError:
        return values


def _repr_type(
    type_: typing.Union[typing.Type[typing.Any], typing.Tuple[typing.Type[typing.Any]]],
) -> str:
    """Return a string representation of the field type."""
    if isinstance(type_, typing._SpecialForm):
        return type_._name

    if is_iterable(type_):
        return " | ".join([_repr_type(arg) for arg in type_])

    if is_generic_type(type_):
        return f"{type_.__origin__.__name__}[{' | '.join([_repr_type(arg) for arg in typing.get_args(type_)])}]"

    return type_.__name__


class FieldBaseMeta(type):
    def __new__(cls, name, bases, attrs):
        new_cls = super().__new__(cls, name, bases, attrs)
        new_cls._nulls = _prep_values(new_cls.null_values)  # type: ignore
        new_cls._blanks = _prep_values(new_cls.blank_values)  # type: ignore
        new_cls.default_validators = frozenset(
            validators.load_validators(*new_cls.default_validators)
        )  # type: ignore
        return new_cls


class FieldBase(typing.Generic[_T], metaclass=FieldBaseMeta):
    """Attribute descriptor for enforcing type validation and constraints."""

    default_validators: typing.Iterable[_FieldValidator[_T, typing.Any]] = []
    blank_values = {
        "",
    }
    null_values = {
        None,
    }
    _blanks: typing.Union[
        typing.FrozenSet[typing.Any], typing.Tuple[typing.Any, ...]
    ] = frozenset()
    _nulls: typing.Union[
        typing.FrozenSet[typing.Any], typing.Tuple[typing.Any, ...]
    ] = frozenset()

    def __init__(
        self,
        type_: typing.Union[
            typing.Type[_T], typing.Type[undefined], typing.Tuple[typing.Type[_T], ...]
        ],
        lazy: bool = False,
        alias: typing.Optional[str] = None,
        allow_null: bool = False,
        allow_blank: bool = True,
        required: bool = False,
        validators: typing.Optional[typing.Iterable[_FieldValidator[_T, _V]]] = None,
        default: typing.Union[_T, DefaultFactory[_T], typing.Type[empty]] = empty,
        on_setattr: typing.Optional[typing.Callable[[typing.Any], typing.Any]] = None,
    ):
        """
        Initialize the field.

        :param type_: The expected type for field values.
        :param alias: Optional string for alternative field naming, defaults to None.
        :param allow_null: If True, permits None values, defaults to False.
        :param allow_blank: If True, permits blank values, defaults to True.
        :param required: If True, field values must be explicitly provided, defaults to False.
        :param validators: A list of validation functions to apply to the field's value, defaults to None.
            Validators should be callables that accept the field value and the optional field instance as arguments.
            NOTE: Values returned from the validators are not used, but they should raise a FieldError if the value is invalid.
        :param default: A default value for the field to be used if no value is set, defaults to empty.
        :param on_setattr: Callable to run on the value before setting it, defaults to None.
            Use this to modify the value before it is validated and set on the instance.
        """
        self.type_ = type_
        self._lazy = lazy
        self.alias = alias
        self.allow_null = allow_null
        self.allow_blank = allow_blank
        self.required = required
        self._validators = list(validators or [])
        self._default = default
        self._parent = None
        self._name = None
        self.on_setattr = on_setattr
        self._init_args = ()
        self._init_kwargs = {}
        self._pending = {}
        self._values = {}

    def post_init_validate(self):
        """
        Validate the field after initialization.

        This method is called after the field is initialized to perform additional validation
        to ensure that the field is correctly configured.
        """
        if not _is_type(self.type_):
            raise TypeError(f"Specified type '{self.type_}' is not a valid type.")

        for validator in self.validators:
            if not callable(validator):
                raise TypeError(f"Field validator '{validator}' is not callable.")

        if self.on_setattr and not callable(self.on_setattr):
            raise TypeError("on_setattr must be a callable.")

        no_default = self._default is empty
        if self.required and not no_default:
            raise FieldError("A default value is not necessary when required=True")

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._init_args = args
        instance._init_kwargs = kwargs
        return instance

    @typing.overload
    def get_name(self, raise_no_name: bool = True) -> str: ...

    @typing.overload
    def get_name(self, raise_no_name: bool = False) -> typing.Optional[str]: ...

    def get_name(
        self, raise_no_name: bool = True
    ) -> typing.Union[str, typing.Optional[str]]:
        """Get the effective name of the field."""
        name = self._name or self.alias
        if raise_no_name and name is None:
            raise FieldError(
                f"{type(self).__name__} has no name. Ensure it has been bound to a parent class or provide an alias."
            )
        return name

    @functools.cached_property
    def validators(self):
        """Return the set of field validators."""
        return frozenset(
            [
                *validators.load_validators(*self._validators),
                *type(self).default_validators,
            ]
        )

    def get_default(self) -> typing.Union[_T, typing.Type[empty]]:
        """Return the default value for the field."""
        if self._default is empty:
            return empty

        if callable(self._default):
            return self._default()  # type: ignore
        return self._default

    def __set_name__(
        self,
        owner: typing.Type[FieldBase],
        name: str,
    ):
        """Assign the field name when the descriptor is initialized on the class."""
        self.bind(owner, name)

    @typing.overload
    def __get__(
        self,
        instance: FieldBase,
        owner: typing.Optional[typing.Type[FieldBase]],
    ) -> typing.Union[_T, typing.Any]: ...

    @typing.overload
    def __get__(
        self,
        instance: typing.Optional[FieldBase],
        owner: typing.Type[FieldBase],
    ) -> Self: ...

    def __get__(
        self,
        instance: typing.Optional[FieldBase],
        owner: typing.Optional[typing.Type[FieldBase]],
    ) -> typing.Union[_T, typing.Any, Self]:
        """Retrieve the field value from an instance or return the default if unset."""
        if instance is None:
            return self

        try:
            return self.getvalue(instance)
        except KeyError as exc:
            raise FieldError(
                f"'{type(instance).__name__}.{self.get_name()}' has no defined value. Provide a default or set required=True."
            ) from exc

    def getvalue(self, instance: FieldBase) -> typing.Union[_T, typing.Any]:
        field_name = self.get_name()

        values = instance._values
        if field_name not in values:
            value = instance._pending[field_name]
            self.setvalue(instance, value, validate=True)
        return values[field_name]

    def __set__(self, instance: FieldBase, value: typing.Any):
        """Set and validate the field value on an instance."""
        _value = value
        if self.on_setattr:
            _value = self.on_setattr(value)

        if _value is empty:
            if self.required:
                raise FieldError(
                    f"'{type(instance).__name__}.{self.get_name()}' is a required field."
                )
            return

        validate = not self._lazy
        self.setvalue(instance, _value, validate)

    def setvalue(self, instance: FieldBase, value: typing.Any, validate: bool = True):
        field_name = self.get_name()

        if not validate:
            if isinstance(value, Field) and not value.is_bound():
                value.bind(type(self), self._name)
            instance._pending[field_name] = value
            instance._values.pop(field_name, None)
            return

        validated_value = self.validate(value, instance)
        if isinstance(validated_value, FieldBase) and not validated_value.is_bound():
            validated_value.bind(type(self), self._name)

        instance._values[field_name] = validated_value
        instance._pending.pop(field_name, None)

    def check_type(self, value: typing.Any) -> typing.TypeGuard[_T]:
        """Check if the value is of the expected type."""
        if self.type_ is undefined:
            return True
        return isinstance(value, self.type_)

    def bind(
        self,
        parent: typing.Optional[typing.Type[FieldBase]],
        name: typing.Optional[str],
    ) -> Self:
        """
        Bind the field to a parent class, assign the field name, etc.
        """
        self._name = name
        self._parent = parent
        return self

    def is_bound(self) -> bool:
        """Return True if the field is bound to a parent class."""
        return bool(self._parent and issubclass(self._parent, FieldBase) and self._name)

    def validate(
        self, value: typing.Any, instance: typing.Optional[FieldBase]
    ) -> typing.Optional[_T]:
        """
        Casts the value to the field's type, validates it, and runs any field validators.

        Override/extend this method to add custom validation logic.
        """
        if self.is_null(value):
            if self.allow_null:
                return None
            raise FieldError(
                f"'{self.get_name()}' is not nullable but got null value '{value}'."
            )

        if self.is_blank(value):
            if self.allow_blank:
                # Return the value as is if it is blank
                return value
            raise FieldError(
                f"'{self.get_name()}' cannot be blank but got blank value '{value}'."
            )

        try:
            if self.check_type(value):
                casted = value
            else:
                casted = self.cast_to_type(value)
            validated = self.run_validators(casted, instance)
        except (ValueError, TypeError) as exc:
            raise FieldError(str(exc), self.get_name()) from exc

        return validated

    def run_validators(
        self,
        value: typing.Union[_T, typing.Any],
        instance: typing.Optional[FieldBase],
    ):
        """Run all field validators on the provided value."""
        for validator in self.validators:
            validator(value, self, instance)
        return value

    def __delete__(self, instance: FieldBase):
        try:
            del instance._values[self.get_name()]
        except KeyError:
            # Ignore if the field value is not set
            pass

    # Allow generic typing checking for fields.
    def __class_getitem__(cls, *args, **kwargs):
        return cls

    def cast_to_type(self, value: typing.Any) -> typing.Union[_T, typing.Any]:
        """
        Cast the value to the field's specified type, if necessary.

        Converts the field's value to the specified type before it is set on the instance.
        """
        if self.check_type(value):
            return value
        return self.type_(value)  # type: ignore

    def is_blank(self, value: typing.Union[_T, typing.Any]) -> bool:
        """
        Return True if the value is blank, else False.
        """

        blanks = type(self)._blanks
        if not blanks:
            return False

        try:
            return value in blanks
        except TypeError:
            return value in list(blanks)

    def is_null(self, value: typing.Any) -> bool:
        """
        Return True if the value is null, else False.
        """
        nulls = type(self)._nulls
        if not nulls:
            return False
        try:
            return value in nulls
        except TypeError:
            return value in list(nulls)

    def to_json(self, instance: FieldBase) -> typing.Any:
        """
        Return a JSON serializable representation of the field's value on the instance.
        """
        field_name = self.get_name()
        value = self.__get__(instance, owner=type(instance))

        try:
            if isinstance(value, FieldBase):
                return value.to_json(self)
            return value
        except (TypeError, ValueError) as exc:
            raise FieldError(
                f"Failed to serialize '{type(instance).__name__}.{field_name}'. ",
                field_name,
            ) from exc

    NO_DEEPCOPY_ARGS: typing.Set[int] = {}
    """
    Indices of arguments that should not be deepcopied when copying the field.

    This is useful for arguments that are immutable or should not be copied to avoid shared state.
    """
    NO_DEEPCOPY_KWARGS: typing.Set[str] = {
        "validators",
        "regex",
    }
    """
    Names of keyword arguments that should not be deepcopied when copying the field.

    This is useful for arguments that are immutable or should not be copied to avoid shared state.
    """

    def __deepcopy__(self, memo):
        args = [
            (
                copy.deepcopy(arg, memo)
                if index not in type(self).NO_DEEPCOPY_ARGS
                else arg
            )
            for index, arg in enumerate(self._init_args)
        ]
        kwargs = {
            key: (
                copy.deepcopy(value, memo)
                if value not in type(self).NO_DEEPCOPY_KWARGS
                else value
            )
            for key, value in self._init_kwargs.items()
        }
        field_copy = self.__class__(*args, **kwargs)
        field_copy._values = merge_mappings(
            field_copy._values,
            copy.deepcopy(self._values, memo),
        )

        if self.is_bound():
            field_copy.bind(self._parent, self._name)
        return field_copy


_Field_co = typing.TypeVar("_Field_co", bound=FieldBase, covariant=True)


def _get_fields(cls: typing.Type) -> typing.Dict[str, FieldBase]:
    fields = {}
    for key, value in cls.__dict__.items():
        if isinstance(value, FieldBase):
            fields[key] = value
    return fields


class FieldMeta(FieldBaseMeta):
    """Metaclass for Field types"""

    def __new__(cls, name, bases, attrs):
        fields = {}
        for key, value in attrs.items():
            if isinstance(value, FieldBase):
                value.post_init_validate()
                fields[key] = value

        def _by_name(item: typing.Tuple[str, FieldBase]) -> str:
            return item[1]._name or item[0]

        for cls_ in bases:
            for c in cls_.mro()[:-1]:
                if issubclass(c, FieldBase) and hasattr(c, "__fields__"):
                    fields.update(c.__fields__)  # type: ignore
                else:
                    found_fields = _get_fields(c)
                    if not found_fields:
                        continue

                    for key, field in found_fields.items():
                        field.post_init_validate()
                        fields[key] = field

        sort_fields = attrs.get("sort_fields", True)
        if sort_fields:
            if callable(sort_fields):
                sort_key = sort_fields
            else:
                sort_key = _by_name
            fields = dict(sorted(fields.items(), key=sort_key))

        # Make read-only to prevent accidental modification
        attrs["__fields__"] = MappingProxyType(fields)
        return super().__new__(cls, name, bases, attrs)


class Field(FieldBase[_T], metaclass=FieldMeta):
    """Attribute descriptor for enforcing type validation and constraints."""

    sort_fields: typing.Union[
        bool, typing.Callable[[typing.Tuple[str, FieldBase]], typing.Any]
    ] = True
    """
    If True, sort the fields by name (in ascending order) on class initialization.

    If a callable is provided, it will be used to sort the fields.

    Useful if you need the field data to be loaded in a specific order on serialization/deserialization.
    """


class FieldInitKwargs(typing.Generic[_T], typing.TypedDict, total=False):
    """Possible keyword arguments for initializing a field."""

    alias: typing.Optional[str]
    """Optional string for alternative field naming."""
    lazy: bool
    """If True, the field will not be validated until it is accessed."""
    allow_null: bool
    """If True, permits the field to be set to None."""
    allow_blank: bool
    """If True, permits the field to be set to a blank value."""
    required: bool
    """If True, the field must be explicitly provided."""
    validators: typing.Optional[typing.Iterable[_FieldValidator[_T, FieldBase]]]
    """A list of validation functions to apply to the field's value."""
    default: typing.Union[_T, DefaultFactory, typing.Type[empty]]
    """A default value for the field to be used if no value is set."""
    on_setattr: typing.Optional[typing.Callable[[typing.Any], typing.Any]]
    """
    Callable to run on the value before setting it. 
    
    Use this to modify the value before it is validated and set on the instance.
    """


class AnyField(Field[typing.Any]):
    """Field for handling values of any type."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[typing.Any]]):
        kwargs.setdefault("allow_null", True)
        super().__init__(type_=undefined, **kwargs)


class BooleanField(Field[bool]):
    """Field for handling boolean values."""

    TRUTHY_VALUES = {
        True,
        1,
        "1",
        iexact("true"),
        iexact("yes"),
    }
    FALSY_VALUES = {  # Use sets for faster lookups
        False,
        0,
        "0",
        iexact("false"),
        iexact("no"),
        iexact("nil"),
        iexact("null"),
        iexact("none"),
    }

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[bool]]):
        kwargs.setdefault("allow_null", True)
        super().__init__(type_=bool, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value

        if value in type(self).TRUTHY_VALUES:
            return True
        if value in type(self).FALSY_VALUES:
            return False
        return bool(value)


@typing.no_type_check
class MinMaxValueMixin(typing.Generic[_T]):
    def __init__(
        self,
        type_: typing.Type[_T],
        *,
        min_value: typing.Optional[_T] = None,
        max_value: typing.Optional[_T] = None,
        **kwargs,
    ):
        """
        Initialize the field.

        :param min_value: The minimum value allowed for the field.
        :param max_value: The maximum value allowed for the field.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(type_=type_, **kwargs)
        self.min_value = min_value
        self.max_value = max_value
        if self.min_value:
            self._validators.append(validators.gte(self.min_value))
        if self.max_value:
            self._validators.append(validators.lte(self.max_value))

    def post_init_validate(self):
        super().post_init_validate()
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise FieldError("min_value cannot be greater than max_value")


class FloatField(MinMaxValueMixin[float], Field[float]):
    """Field for handling float values."""

    min_value = Field(float, allow_null=True, required=True)
    max_value = Field(float, allow_null=True, required=True)

    def __init__(
        self,
        *,
        min_value: typing.Optional[float] = None,
        max_value: typing.Optional[float] = None,
        **kwargs: Unpack[FieldInitKwargs[float]],
    ):
        kwargs["allow_blank"] = False  # Floats cannot be blank
        super().__init__(
            type_=float,
            min_value=min_value,
            max_value=max_value,
            **kwargs,
        )


class IntegerField(MinMaxValueMixin[int], Field[int]):
    """Field for handling integer values."""

    min_value = Field(int, allow_null=True, required=True)
    max_value = Field(int, allow_null=True, required=True)

    def __init__(
        self,
        *,
        min_value: typing.Optional[int] = None,
        max_value: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs[int]],
    ):
        kwargs["allow_blank"] = False  # Integers cannot be blank
        super().__init__(
            type_=int,
            min_value=min_value,
            max_value=max_value,
            **kwargs,
        )


class StringField(Field[str]):
    """Field for handling string values."""

    DEFAULT_MIN_LENGTH: typing.Optional[int] = None
    """Default minimum length of values."""
    DEFAULT_MAX_LENGTH: typing.Optional[int] = None
    """Default maximum length of values."""

    min_length = IntegerField(allow_null=True, validators=[validators.gte(0)])
    max_length = IntegerField(allow_null=True, validators=[validators.gte(0)])
    to_lowercase = BooleanField()
    to_uppercase = BooleanField()

    def __init__(
        self,
        *,
        min_length: typing.Optional[int] = None,
        max_length: typing.Optional[int] = None,
        trim_whitespaces: bool = True,
        to_lowercase: bool = False,
        to_uppercase: bool = False,
        **kwargs: Unpack[FieldInitKwargs[str]],
    ):
        """
        Initialize the field.

        :param min_length: The minimum length allowed for the field's value.
        :param max_length: The maximum length allowed for the field's value.
        :param trim_whitespaces: If True, leading and trailing whitespaces will be removed.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(type_=str, **kwargs)
        self.min_length = min_length or type(self).DEFAULT_MIN_LENGTH
        self.max_length = max_length or type(self).DEFAULT_MAX_LENGTH
        if self.min_length:
            self._validators.append(validators.min_len(self.min_length))
        if self.max_length:
            self._validators.append(validators.max_len(self.max_length))

        self.trim_whitespaces = trim_whitespaces
        self.to_lowercase = to_lowercase
        self.to_uppercase = to_uppercase

    def post_init_validate(self):
        super().post_init_validate()
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("min_length cannot be greater than max_length")

        if self.to_lowercase and self.to_uppercase:
            raise FieldError("`to_lowercase` and `to_uppercase` cannot both be truthy")

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value

        casted = str(value)
        if self.trim_whitespaces:
            casted = casted.strip()
        if self.to_lowercase:
            return casted.lower()
        if self.to_uppercase:
            return casted.upper()
        return casted


class DictField(Field[typing.Dict]):
    """Field for handling dictionary values."""

    blank_values = [
        {},
    ]

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[typing.Dict]]):
        super().__init__(dict, **kwargs)


class UUIDField(Field[uuid.UUID]):
    """Field for handling UUID values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[uuid.UUID]]):
        super().__init__(type_=uuid.UUID, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)

    def to_json(self, instance: FieldBase) -> str:
        value = self.__get__(instance, owner=type(instance))
        return str(value)


def _on_set_child(value: typing.Union[typing.Any, Field[_V]]):
    if isinstance(value, Field):
        return copy.deepcopy(value)
    return value


@typing.no_type_check
class IterFieldBase(typing.Generic[_V, _T]):
    """Mixin for iterable fields."""

    blank_values = [[], tuple(), set()]

    child = Field(Field[_V], on_setattr=_on_set_child)
    size = IntegerField(allow_null=True, validators=[validators.gt(0)])

    def __init__(
        self,
        type_: typing.Type[_T],
        child: typing.Optional[Field[_V]] = None,
        *,
        size: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs[_T]],
    ):
        """
        Initialize the field.

        :param type_: The expected iterable type for the field.
        :param child: Optional field for validating elements in the field's value.
        :param size: Optional size constraint for the iterable.
        """
        if not is_iterable_type(type_, exclude=(str, bytes)):
            raise TypeError(
                "Specified type must be an iterable type; excluding str or bytes."
            )
        super().__init__(type_=type_, **kwargs)

        self.child = child or AnyField()
        self.size = size
        if self.size:
            self._validators.append(validators.max_len(self.size))

    def validate(
        self, value: typing.Any, instance: typing.Optional["_Field_co"]
    ) -> typing.Optional[_T]:
        validated_value: typing.Optional[_T] = super().validate(value, instance)
        if not validated_value:
            return validated_value

        return type(validated_value)(
            self.child.validate(item, instance)
            for item in validated_value  # type: ignore
        )

    def check_type(self, value: typing.Any) -> bool:
        if not super().check_type(value):
            return False

        if value and self.child.type_ is not undefined:
            for item in value:
                if not self.child.check_type(item):
                    return False
        return True

    def cast_to_type(self, value: typing.Any):
        # Cast container to the expected type first
        casted = super().cast_to_type(value)
        if self.child.type_ is undefined:
            return casted

        # Then, cast each element in the container to the child field's type
        return type(casted)(
            (item if self.child.check_type(item) else self.child.cast_to_type(item))
            for item in casted
        )

    def to_json(self, instance: FieldBase) -> typing.Optional[typing.List[typing.Any]]:
        value = self.__get__(instance, owner=type(instance))
        if value is None:
            return None
        return [
            (item.to_json(self) if isinstance(item, Field) else item) for item in value
        ]


class ListField(IterFieldBase[_V, typing.List[_V]], Field[typing.List[_V]]):
    """Field for lists, with optional validation of list elements through the `child` field."""

    def __init__(
        self,
        child: typing.Optional[Field[_V]] = None,
        *,
        size: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs[typing.List[_V]]],
    ):
        super().__init__(type_=list, child=child, size=size, **kwargs)


class SetField(IterFieldBase[_V, typing.Set[_V]], Field[typing.Set[_V]]):
    """Field for sets, with optional validation of set elements through the `child` field."""

    def __init__(
        self,
        child: typing.Optional[Field[_V]] = None,
        *,
        size: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs[typing.Set[_V]]],
    ):
        super().__init__(type_=set, child=child, size=size, **kwargs)


class TupleField(IterFieldBase[_V, typing.Tuple[_V]], Field[typing.Tuple[_V]]):
    """Field for tuples, with optional validation of tuple elements through the `child` field."""

    def __init__(
        self,
        child: typing.Optional[Field[_V]] = None,
        *,
        size: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs[typing.Tuple[_V]]],
    ):
        super().__init__(type_=tuple, child=child, size=size, **kwargs)


class DecimalField(Field[decimal.Decimal]):
    """Field for handling decimal values."""

    dp = IntegerField(allow_null=True)

    def __init__(
        self,
        dp: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs[decimal.Decimal]],
    ):
        """
        Initialize the field.

        :param dp: The number of decimal places to round the field's value to.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(type_=decimal.Decimal, **kwargs)
        self.dp = dp

    def cast_to_type(self, value):
        if self.check_type(value):
            return value

        casted = decimal.Decimal(value)
        if self.dp:
            return casted.quantize(decimal.Decimal(f"0.{'0'*(self.dp - 1)}1"))
        return casted

    def to_json(self, instance: FieldBase) -> str:
        value = self.__get__(instance, owner=type(instance))
        return str(value)


_email_validator = validators.pattern(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    message="'{name}' must be a valid email address.",
)
_email_validator.requires_context = True


class EmailField(StringField):
    """Field for handling email addresses."""

    default_validators = (_email_validator,)

    def __init__(
        self,
        *,
        min_length=None,
        max_length=None,
        trim_whitespaces=True,
        to_lowercase=True,  # Field prefers to store email values in lowercase
        to_uppercase=False,
        **kwargs,
    ):
        super().__init__(
            min_length=min_length,
            max_length=max_length,
            trim_whitespaces=trim_whitespaces,
            to_lowercase=to_lowercase,
            to_uppercase=to_uppercase,
            **kwargs,
        )


class URLField(Field[Url]):
    """Field for handling URL values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[Url]]):
        super().__init__(type_=Url, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value
        return parse_url(str(value))

    def to_json(self, instance: FieldBase) -> str:
        value = self.__get__(instance, owner=type(instance))
        return str(value)


class ChoiceFieldBase(typing.Generic[_T]):
    """Mixin base for choice fields."""

    choices = ListField(
        required=True, allow_blank=False, validators=[validators.min_len(2)]
    )

    @typing.no_type_check
    def __init__(self, choices: typing.List[_T], **kwargs: Unpack[FieldInitKwargs[_T]]):
        super().__init__(**kwargs)
        self.choices = choices

    @typing.no_type_check
    def validate(
        self, value: typing.Any, instance: typing.Optional["_Field_co"]
    ) -> typing.Optional[_T]:
        value = super().validate(value, instance)
        if value is None:
            return None

        if value not in self.choices:
            raise FieldError(f"'{self.get_name()}' must be one of {self.choices!r}.")
        return value


class ChoiceField(ChoiceFieldBase, AnyField):
    """Field for with predefined choices for values."""

    pass


class StringChoiceField(ChoiceFieldBase[str], StringField):
    """String field with predefined choices for values."""

    pass


class IntegerChoiceField(ChoiceFieldBase[int], IntegerField):
    """Integer field with predefined choices for values."""

    pass


class FloatChoiceField(ChoiceFieldBase[float], FloatField):
    """Float field with predefined choices for values."""

    pass


class TypedChoiceField(ChoiceFieldBase[_T], Field[_T]):
    """Choice field with defined type enforcement."""

    def __init__(
        self,
        type_: typing.Type[_T],
        *,
        choices: typing.List[_T],
        **kwargs: Unpack[FieldInitKwargs[_T]],
    ):
        """
        Initialize the field.

        :param type_: The expected type for choice field's values.
        :param choices: A list of valid choices for the field.
        """
        super().__init__(choices=choices, type_=type_, **kwargs)  # type: ignore


_DEFAULT_JSON_TYPES = (dict, list, str, int, float, bool, NoneType)


class JSONField(Field[typing.Union[dict, list, str, int, float, bool, NoneType]]):
    """Field for handling JSON data."""

    JSON_TYPES = _DEFAULT_JSON_TYPES

    def __init__(
        self,
        **kwargs: Unpack[
            FieldInitKwargs[typing.Union[dict, list, str, int, float, bool, NoneType]]
        ],
    ):
        super().__init__(type_=type(self).JSON_TYPES, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value
        return json.dumps(value)

    def to_json(self, instance: FieldBase):
        value = self.__get__(instance, owner=type(instance))
        if value is None:
            return None

        if self.check_type(value):
            return value
        return json.loads(value)


_hex_color_validator = validators.pattern(
    r"^#(?:[0-9a-fA-F]{3,4}){1,2}$",
    message="'{name}' must be a valid hex color code.",
)

_hex_color_validator.requires_context = True


class HexColorField(StringField):
    """Field for handling hex color values."""

    # DEFAULT_MIN_LENGTH = 4
    # DEFAULT_MAX_LENGTH = 9
    default_validators = (_hex_color_validator,)


_rgb_color_validator = validators.pattern(
    r"^rgb[a]?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(\d{1,3})\s*)?\)$",
    message="'{name}' must be a valid RGB color code.",
)
_rgb_color_validator.requires_context = True


class RGBColorField(StringField):
    """Field for handling RGB color values."""

    # DEFAULT_MAX_LENGTH = 38
    default_validators = (_rgb_color_validator,)

    def __init__(
        self,
        *,
        min_length=None,
        max_length=None,
        trim_whitespaces=True,
        **kwargs,
    ):
        # Field enforces lowercase for RGB color values
        kwargs["to_lowercase"] = True
        kwargs["to_uppercase"] = False
        super().__init__(
            min_length=min_length,
            max_length=max_length,
            trim_whitespaces=trim_whitespaces,
            **kwargs,
        )


_hsl_color_validator = validators.pattern(
    r"^hsl[a]?\(\s*(\d{1,3})\s*,\s*(\d{1,3})%?\s*,\s*(\d{1,3})%?\s*(?:,\s*(\d{1,3})\s*)?\)$",
    message="'{name}' must be a valid HSL color code.",
)
_hsl_color_validator.requires_context = True


class HSLColorField(StringField):
    """Field for handling HSL color values."""

    # DEFAULT_MAX_LENGTH = 40
    default_validators = (_hsl_color_validator,)

    def __init__(
        self,
        *,
        min_length=None,
        max_length=None,
        trim_whitespaces=True,
        **kwargs,
    ):
        # Field enforces lowercase for HSL color values
        kwargs["to_lowercase"] = True
        kwargs["to_uppercase"] = False
        super().__init__(
            min_length=min_length,
            max_length=max_length,
            trim_whitespaces=trim_whitespaces,
            **kwargs,
        )


_slug_validator = validators.pattern(
    r"^[a-zA-Z0-9_-]+$",
    message="'{name}' must be a valid slug.",
)
_slug_validator.requires_context = True


class SlugField(StringField):
    """Field for URL-friendly strings."""

    default_validators = (_slug_validator,)


class IPAddressField(Field[typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]):
    """Field for hanling IP addresses."""

    def __init__(
        self,
        **kwargs: Unpack[
            FieldInitKwargs[typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]
        ],
    ):
        super().__init__(type_=(ipaddress.IPv4Address, ipaddress.IPv6Address), **kwargs)

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value
        return ipaddress.ip_address(value)

    def to_json(self, instance: FieldBase):
        """Return a JSON representation of the field's value."""
        value = self.__get__(instance, owner=type(instance))
        if value is None:
            return None
        return value.exploded


def _parse_duration(s, /) -> datetime.timedelta:
    duration = parse_duration(s)
    if duration is None:
        raise ValueError(f"Invalid duration value - {s}")
    return duration


class DurationField(Field[datetime.timedelta]):
    """Field for handling duration values."""

    parser = Field[typing.Callable[[str], datetime.timedelta]](
        undefined, allow_null=False, validators=[validators.is_callable]
    )

    def __init__(
        self,
        parser: typing.Optional[typing.Callable[[str], datetime.timedelta]] = None,
        **kwargs: Unpack[FieldInitKwargs[datetime.timedelta]],
    ):
        super().__init__(type_=datetime.timedelta, **kwargs)
        self.parser = parser or _parse_duration

    def cast_to_type(self, value: typing.Any) -> datetime.timedelta:
        if self.check_type(value):
            return value

        if not isinstance(value, str):
            raise FieldError(f"Invalid duration value - {value}")

        try:
            return self.parser(value)
        except ValueError as exc:
            raise FieldError(f"Invalid duration value - {value}") from exc

    def to_json(self, instance: FieldBase) -> typing.Optional[str]:
        value = self.__get__(instance, owner=type(instance))
        if value is None:
            return None
        return str(value)


TimeDeltaField = DurationField


class TimeZoneField(Field[datetime.tzinfo]):
    """Field for handling timezone values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[datetime.tzinfo]]):
        super().__init__(type_=datetime.tzinfo, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value
        return zoneinfo.ZoneInfo(value)

    def to_json(self, instance: FieldBase) -> str:
        value = self.__get__(instance, owner=type(instance))
        return str(value)


DatetimeStr = str
DatetimeFormat = str
DatetimeParser = typing.Callable[
    [
        DatetimeStr,
        typing.Optional[typing.Union[DatetimeFormat, typing.Iterable[DatetimeFormat]]],
    ],
    datetime.datetime,
]


@typing.no_type_check
class DateTimeFieldBase(typing.Generic[_T]):
    """Mixin base for datetime fields."""

    DEFAULT_OUTPUT_FORMAT: str = "%Y-%m-%d %H:%M:%S%z"

    input_formats = SetField(
        child=StringField(allow_null=False, allow_blank=False),
        allow_null=True,
        allow_blank=False,
    )
    output_format = StringField(allow_null=True, allow_blank=False)
    parser = Field[DatetimeParser](
        undefined, allow_null=False, validators=[validators.is_callable]
    )

    def __init__(
        self,
        type_: typing.Type[_T],
        *,
        input_formats: typing.Optional[typing.Iterable[str]] = None,
        output_format: typing.Optional[str] = None,
        parser: typing.Optional[DatetimeParser] = None,
        **kwargs: Unpack[FieldInitKwargs[_T]],
    ):
        """
        Initialize the field.

        :param input_formats: Possible expected input format (ISO or RFC) for the date value.
            If not provided, the field will attempt to parse the date value
            itself, which may be slower.

        :param output_format: The preferred output format for the date value.
        :param parser: A custom parser function for parsing the date value.
            Serialization speed of field will be dependent on the parser function.
            The parse should take a string and an optional format string or list of formats.

        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(type_=type_, **kwargs)
        self.input_formats = input_formats
        self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT
        self.parser = parser or iso_parse

    def cast_to_type(self, value: typing.Any) -> typing.Union[_T, typing.Any]:
        if self.check_type(value):
            return value

        if not isinstance(value, str):
            raise FieldError(f"Invalid value - {value}")

        try:
            return self.parser(value, self.input_formats)
        except ValueError as exc:
            raise FieldError(f"Invalid value - {value}") from exc

    def to_json(self, instance: FieldBase) -> typing.Optional[str]:
        value = self.__get__(instance, owner=type(instance))
        if value is None:
            return None
        return value.strftime(self.output_format)


class DateField(DateTimeFieldBase[datetime.date], Field[datetime.date]):
    """Field for handling date values."""

    DEFAULT_OUTPUT_FORMAT = "%Y-%m-%d"

    def __init__(
        self,
        *,
        input_formats: typing.Optional[typing.Iterable[str]] = None,
        output_format: typing.Optional[str] = None,
        parser: typing.Optional[DatetimeParser] = None,
        **kwargs: Unpack[FieldInitKwargs[datetime.date]],
    ):
        """
        Initialize the field.

        :param input_formats: Possible expected input format (ISO or RFC) for the date value.
            If not provided, the field will attempt to parse the date value
            itself, which may be slower.

        :param output_format: The preferred output format for the date value.
        :param parser: A custom parser function for parsing the date value.
            Serialization speed of field will be dependent on the parser function.
            The parse should take a string and an optional format string or list of formats.

        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(
            type_=datetime.date,
            input_formats=input_formats,
            output_format=output_format,
            parser=parser,
            **kwargs,
        )


class TimeField(DateTimeFieldBase[datetime.date], Field[datetime.time]):
    """Field for handling time values."""

    DEFAULT_OUTPUT_FORMAT = "%H:%M:%S.%s"

    def __init__(
        self,
        *,
        input_formats: typing.Optional[typing.Iterable[str]] = None,
        output_format: typing.Optional[str] = None,
        parser: typing.Optional[DatetimeParser] = None,
        **kwargs: Unpack[FieldInitKwargs[datetime.time]],
    ):
        """
        Initialize the field.

        :param input_format: Possible expected input format (ISO or RFC) for the time value.
            If not provided, the field will attempt to parse the time value
            itself, which may be slower.

        :param output_format: The preferred output format for the time value.
        :param parser: A custom parser function for parsing the time value.
            Serialization speed of field will be dependent on the parser function.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(
            type_=datetime.time,
            input_formats=input_formats,
            output_format=output_format,
            parser=parser,
            **kwargs,
        )


class DateTimeField(DateTimeFieldBase[datetime.datetime], Field[datetime.datetime]):
    """Field for handling datetime values."""

    DEFAULT_OUTPUT_FORMAT = "%Y-%m-%d %H:%M:%S%z"

    tz = TimeZoneField(allow_null=True)

    def __init__(
        self,
        *,
        input_formats: typing.Optional[typing.Iterable[str]] = None,
        output_format: typing.Optional[str] = None,
        tz: typing.Optional[datetime.tzinfo] = None,
        parser: typing.Optional[DatetimeParser] = None,
        **kwargs: Unpack[FieldInitKwargs[datetime.datetime]],
    ):
        """
        Initialize the field.

        :param input_format: Possible expected input format (ISO or RFC) for the datetime value.
            If not provided, the field will attempt to parse the datetime value
            itself, which may be slower.

        :param output_format: The preferred output format for the datetime value.
        :param tz: The timezone to use for the datetime value. If this set,
            the datetime value will be represented in this timezone.

        :param parser: A custom parser function for parsing the datetime value.
            Serialization speed of field will be dependent on the parser function.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(
            type_=datetime.datetime,
            input_formats=input_formats,
            output_format=output_format,
            parser=parser,
            **kwargs,
        )
        self.tz = tz

    def cast_to_type(self, value: typing.Any) -> datetime.datetime:
        if self.check_type(value):
            casted = value
        else:
            if not isinstance(value, str):
                raise FieldError(f"Invalid datetime value - {value}")
            try:
                casted = self.parser(value, self.input_formats)
            except ValueError as exc:
                raise FieldError(f"Invalid datetime value - {value}") from exc

        if self.tz:
            if casted.tzinfo:
                casted = casted.astimezone(self.tz)
            else:
                casted = casted.replace(tzinfo=self.tz)
        return casted


class BytesField(Field[bytes]):
    """Field for handling byte values."""

    encoding = StringField(allow_null=True, allow_blank=False)

    def __init__(
        self, encoding: str = "utf-8", **kwargs: Unpack[FieldInitKwargs[bytes]]
    ):
        """
        Initialize the field.

        :param sencoding: The encoding to use when encoding/decoding byte strings.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(type_=bytes, **kwargs)
        self.encoding = encoding

    def cast_to_type(self, value: typing.Any):
        if self.check_type(value):
            return value

        if isinstance(value, str):
            try:
                return base64.b64decode(value.encode(encoding=self.encoding))
            except (ValueError, TypeError) as exc:
                raise FieldError("Invalid base64 string for bytes") from exc
        return bytes(value)

    def to_json(self, instance: FieldBase):
        """Return a JSON representation of the field's value."""
        value = self.__get__(instance, owner=type(instance))
        if value is None:
            return None
        return base64.b64encode(value).decode(encoding=self.encoding)


class IOField(Field[io.IOBase]):
    """Field for handling file-like I/O objects."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs[io.IOBase]]):
        super().__init__(type_=io.IOBase, **kwargs)

    def to_json(self, instance: FieldBase):
        raise FieldError(f"{type(self).__name__} does not support JSON serialization.")


class FileField(Field[io.BufferedIOBase]):
    """Field for handling files"""

    max_size = IntegerField(allow_null=True, validators=[validators.gte(0)])
    allowed_types = SetField(
        child=StringField(allow_null=False, allow_blank=False, to_lowercase=True),
        allow_null=True,
        allow_blank=False,
    )

    def __init__(
        self,
        max_size: typing.Optional[int] = None,
        allowed_types: typing.Optional[typing.List[str]] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param max_size: The maximum size of the file in bytes.
        :param allowed_types: A list of allowed file types or extensions.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(type_=io.BufferedIOBase, **kwargs)
        self.max_size = max_size
        self.allowed_types = allowed_types or []

    def validate(self, value: typing.Any, instance: typing.Optional[FieldBase]):
        """Validate the file object, checking size and type constraints."""
        file_obj = super().validate(value, instance)
        if file_obj is None:
            return None

        if self.max_size:
            file_obj.seek(0, 2)  # Move to end of file to check size
            file_size = file_obj.tell()
            file_obj.seek(0)  # Reset file pointer to the beginning
            if file_size > self.max_size:
                raise FieldError(f"File exceeds maximum size of {self.max_size} bytes.")

        if self.allowed_types:
            # Check if the file has an allowed type or extension
            if not self.is_allowed_type(file_obj):
                raise FieldError(
                    f"File type not allowed. Allowed types: {self.allowed_types}."
                )

        return file_obj

    def is_allowed_type(self, file_obj: io.BufferedIOBase) -> bool:
        """Check if the file type or extension is allowed."""
        # Example implementation; in a real scenario, you might want to check MIME types
        # or the file extension based on file name or magic numbers.
        file_name = getattr(file_obj, "name", "")
        if not file_name:
            return False
        file_extension = file_name.split(".")[-1].lower()
        if not file_extension:
            return False
        return file_extension in self.allowed_types

    def __delete__(self, instance: FieldBase):
        """Close the file if it was opened through the field."""
        field_value = self.__get__(instance, type(instance))
        if hasattr(field_value, "close"):
            field_value.close()
        super().__delete__(instance)


# These phone number fields are implemented with dependencies on the `phonenumbers` library.
# Hence, the fields are only available when the `phonenumbers` library is installed.
# Here we use a ghost field approach to make the fields available even when the dependencies.
# Although, a DependencyRequired is raised when the fields are initialized without the required
# dependencies installed. This allows other fields in this module to be useable even without
# the dependencies for these fields being installed.
@depends_on({"phonenumbers": "phonenumbers"})
def _PhoneNumberField(**kwargs): ...


@depends_on({"phonenumbers": "phonenumbers"})
def _PhoneNumberStringField(**kwargs): ...


PhoneNumberField = _PhoneNumberField
PhoneNumberStringField = _PhoneNumberStringField

# Makes sure the ghost phonenumber fields are unavailable for import using these names
del _PhoneNumberField, _PhoneNumberStringField


try:
    # This will override the ghost fields above if the `phonenumbers` library is installed
    # and the library is successfully imported. If the `phonenumbers` library is not installed,
    # the fields below will not be available and the ghost phonenumber fields above will be used instead.
    # and a proper warning/error will be displayed when the fields are initialized without the required
    # dependencies installed.
    # This also tricks the typing system into thinking the phonenumber fields are classes even when
    # the ghost phonenumber fields are function-based versions, thereby improving typing for the field.

    # This approach is verbose but this is the best balance I could find as regards proper typing for
    # the field, and field dependency management
    from phonenumbers import PhoneNumber, parse, format_number, PhoneNumberFormat

    class PhoneNumberField(Field[PhoneNumber]):
        """Phone number object field."""

        DEFAULT_OUTPUT_FORMAT = PhoneNumberFormat.E164

        output_format = Field(PhoneNumberFormat)

        def __init__(
            self,
            output_format: typing.Optional[PhoneNumberFormat] = None,
            **kwargs: Unpack[FieldInitKwargs],
        ):
            """
            Initialize the field.

            :param output_format: The preferred output format for the phone number value.
            :param kwargs: Additional keyword arguments for the field.
            """
            super().__init__(type_=PhoneNumber, **kwargs)
            self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT

        def cast_to_type(self, value: typing.Any):
            if self.check_type(value):
                return value

            try:
                return parse(value)
            except Exception as exc:
                raise FieldError(f"Invalid phone number - {value}") from exc

        def to_json(self, instance: FieldBase):
            value = self.__get__(instance, owner=type(instance))
            if value is None:
                return None
            return format_number(value, self.output_format)

    class PhoneNumberStringField(StringField):
        """Phone number string field"""

        DEFAULT_OUTPUT_FORMAT = PhoneNumberFormat.E164

        output_format = Field(PhoneNumberFormat)

        def __init__(
            self,
            output_format: typing.Optional[PhoneNumberFormat] = None,
            **kwargs: Unpack[FieldInitKwargs],
        ):
            """
            Initialize the field.

            :param output_format: The preferred output format for the phone number value.
            :param kwargs: Additional keyword arguments for the field.
            """
            super().__init__(max_length=20, **kwargs)
            self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT

        def cast_to_type(self, value: typing.Any):
            return format_number(parse(value), self.output_format)

        def to_json(self, instance: FieldBase):
            value = self.__get__(instance, owner=type(instance))
            if value is None or isinstance(value, str):
                return value
            # The cast_to_type method already does the formatting
            return self.cast_to_type(value)

except ImportError:
    pass


__all__ = [
    "empty",
    "undefined",
    "FieldError",
    "Field",
    "FieldInitKwargs",
    "AnyField",
    "BooleanField",
    "StringField",
    "FloatField",
    "IntegerField",
    "DictField",
    "ListField",
    "SetField",
    "TupleField",
    "DecimalField",
    "EmailField",
    "URLField",
    "ChoiceFieldBase",
    "ChoiceField",
    "StringChoiceField",
    "IntegerChoiceField",
    "FloatChoiceField",
    "TypedChoiceField",
    "JSONField",
    "HexColorField",
    "RGBColorField",
    "HSLColorField",
    "IPAddressField",
    "SlugField",
    "DateField",
    "TimeField",
    "DurationField",
    "TimeDeltaField",
    "DateTimeField",
    "BytesField",
    "IOField",
    "FileField",
    "PhoneNumberField",
    "PhoneNumberStringField",
    "_Field_co",
]
