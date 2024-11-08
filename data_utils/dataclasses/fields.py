"""Data fields for enforcing type validation and constraints."""

import uuid
import decimal
import datetime
import functools
import typing
import re
import json
import base64
import io
import copy
import ipaddress
from urllib3.util import Url, parse_url

from helpers.utils.misc import is_generic_type, is_iterable_type, is_iterable
from helpers.dependencies import depends_on, deps_required
from ..exceptions import DataError
from ..parsers import parse_duration

try:
    from typing_extensions import Unpack
except ImportError:
    from typing import Unpack

try:
    from typing_extensions import ParamSpec
except ImportError:
    from typing import ParamSpec

from helpers.utils.time import timeit
from helpers.utils.misc import merge_dicts


class empty:
    """Class to represent missing/empty values."""

    pass


class undefined:
    """Class to represent an undefined type."""

    pass


_T = typing.TypeVar("_T")
_P = ParamSpec("_P")
_R = typing.TypeVar("_R")
_V = typing.TypeVar("_V")
FieldValidator: typing.TypeAlias = typing.Callable[[_V, typing.Optional[_R]], _V]
DefaultFactory = typing.Callable[[], _T]


class FieldError(DataError, ValueError):
    """Exception raised for field-related errors."""

    pass


def raiseFieldError(func: typing.Callable[_P, _R]) -> typing.Callable[_P, _R]:
    """Decorator to catch exceptions and raise a FieldError instead."""

    @functools.wraps(func)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        try:
            return func(*args, **kwargs)
        except FieldError:
            raise
        except Exception as exc:
            raise FieldError(exc) from exc

    return wrapper


class FieldMeta(type):
    """Metaclass for Field types"""

    def __new__(meta_cls, name, bases, attrs):
        new_cls = super().__new__(meta_cls, name, bases, attrs)
        meta_cls.clean_null_values(new_cls)
        meta_cls.clean_blank_values(new_cls)
        return new_cls

    @staticmethod
    def clean_blank_values(cls: "_Field"):
        blank_values = getattr(cls, "blank_values", None)
        if blank_values is None:
            return

        if not is_iterable(blank_values):
            raise TypeError("Field blank_values must be an iterable.")

        cls.blank_values = tuple(cls._lower_if_string(value) for value in blank_values)

    @staticmethod
    def clean_null_values(cls: "_Field"):
        null_values = getattr(cls, "null_values", None)
        if null_values is None:
            return

        if not is_iterable(null_values):
            raise TypeError("Field null_values must be an iterable.")

        cls.null_values = tuple(cls._lower_if_string(value) for value in null_values)


class Field(typing.Generic[_T], metaclass=FieldMeta):
    """Attribute descriptor for enforcing type validation and constraints."""

    default_validators: FieldValidator = ()
    default_blank_values = ("",)
    blank_values = ()
    default_null_values = (None,)
    null_values = ()

    __valuestore__: str = "__dict__"
    """Name of the attribute used to store field values on the instance."""

    def __init__(
        self,
        _type: typing.Type[_T],
        *,
        alias: typing.Optional[str] = None,
        allow_null: bool = False,
        allow_blank: bool = True,
        required: bool = False,
        validators: typing.Optional[
            typing.Iterable[FieldValidator[_T, "_Field"]]
        ] = None,
        default: typing.Union[_T, DefaultFactory, typing.Type[empty]] = empty,
        onsetvalue: typing.Optional[typing.Callable[[typing.Any], typing.Any]] = None,
    ):
        """
        Initialize the field.

        :param _type: The expected type for field values.
        :param alias: Optional string for alternative field naming, defaults to None.
        :param allow_null: If True, permits None values, defaults to False.
        :param allow_blank: If True, permits blank values, defaults to True.
        :param required: If True, field values must be explicitly provided, defaults to False.
        :param validators: A list of validation functions to apply to the field's value, defaults to None.
            Validators should be callables that accept the field value and the optional field instance as arguments.
            NOTE: Values returned from the validators are not used, but they should raise a FieldError if the value is invalid.
        :param default: A default value for the field to be used if no value is set, defaults to empty.
        :param onsetvalue: Callable to run on the value before setting it, defaults to None.
            Use this to modify the value before it is validated and set on the instance.
        """
        if not self._object_is_type(_type):
            raise TypeError(f"Specified type '{_type}' is not a valid type.")

        self._type = _type
        self.alias = alias
        self.allow_null = allow_null
        self.allow_blank = allow_blank
        self.required = required
        self.validators = list(validators or [])
        self._default = default
        self._parent = None
        self._name = None

        if onsetvalue and not callable(onsetvalue):
            raise TypeError("onsetvalue must be a callable.")
        self._onsetvalue = onsetvalue

        if self.required and default is not empty:
            raise FieldError("A default value is not necessary when required=True")

        default_value = self.get_default()
        if default_value is not empty:
            if self.allow_null and self.is_null(default_value):
                return
            if not self.check_type(default_value):
                raise FieldError(
                    f"Default value '{default_value}', is not of type '{self._repr_type(self.get_type())}'."
                )
        return

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)
        instance._init_args = args
        instance._init_kwargs = kwargs

        # Setup the valuestore for the instance
        valuestore = getattr(instance, cls.__valuestore__, None)
        if valuestore is None:
            setattr(instance, cls.__valuestore__, {})
        return instance

    @staticmethod
    def _object_is_type(object: object) -> bool:
        """Check if an object is a type."""
        if is_iterable(object):
            return all(isinstance(obj, type) for obj in object)
        return isinstance(object, type)

    @property
    def __values__(self) -> typing.Dict[str, typing.Any]:
        """Return the field values store for the instance."""
        valuestore = getattr(self, type(self).__valuestore__, {})
        return valuestore

    @__values__.setter
    def __values__(self, value):
        setattr(self, type(self).__valuestore__, value)

    def get_name(self, raise_no_name: bool = True) -> typing.Optional[str]:
        """Get the effective name of the field."""
        name = self.alias or self._name

        if raise_no_name and name is None:
            raise FieldError(
                f"{type(self).__name__} has no name. Ensure it has been bound to a parent class or provide an alias."
            )
        return name

    def get_type(self) -> typing.Union[typing.Type[_T], typing.Type[undefined]]:
        """Return the expected type for field values."""
        return self._type

    @property
    def validators(self) -> typing.List[FieldValidator[_T, "_Field"]]:
        """Return the list of field validators."""
        return [*self._validators, *self.default_validators]

    @validators.setter
    def validators(self, value: typing.List[FieldValidator[_T, "_Field"]]):
        for validator in value:
            if not callable(validator):
                raise TypeError(f"Field validator '{validator}' is not callable.")

        self._validators = value

    @validators.deleter
    def validators(self):
        self._validators = []

    def get_default(self) -> _T:
        """Return the default value for the field."""
        if self._default is empty:
            return empty

        if callable(self._default):
            return self._default()
        return self._default

    def __set_name__(
        self,
        owner: typing.Type["_Field"],
        name: str,
    ):
        """Assign the field name when the descriptor is initialized on the class."""
        if not issubclass(owner, Field):
            raise TypeError(
                f"{type(self).__name__} must be defined within a Field subclass."
            )

        self.bind(owner, name)

    @raiseFieldError
    def __get__(
        self,
        instance: typing.Optional["_Field"],
        owner: typing.Optional[typing.Type["_Field"]],
    ):
        """Retrieve the field value from an instance or return the default if unset."""
        if instance is None:
            return self

        field_name = self.get_name()
        value: _T = instance.__values__.get(field_name, self.get_default())
        if value is empty:
            raise FieldError(
                f"'{type(instance).__name__}.{field_name}' has no defined value. Provide a default or set required=True."
            )
        return value

    @raiseFieldError
    def __set__(self, instance: "_Field", value: typing.Any):
        """Set and validate the field value on an instance."""
        field_name = self.get_name()
        if value is empty:
            if self.required:
                raise FieldError(
                    f"'{type(instance).__name__}.{field_name}' is a required field."
                )
            return

        if callable(self._onsetvalue):
            value = self._onsetvalue(value)

        validated_value = self.validate(value, instance)
        if isinstance(validated_value, Field) and not validated_value.is_bound():
            validated_value.bind(type(self), self._name)
        instance.__values__[field_name] = validated_value

    def check_type(self, value: typing.Any) -> typing.TypeGuard[_T]:
        """Check if the value is of the expected type."""
        if self.get_type() is undefined:
            return True
        return isinstance(value, self.get_type())

    def bind(
        self,
        parent: typing.Optional[typing.Type["_Field"]],
        name: str,
    ):
        """
        Bind the field to a parent class, assign the field name, etc.
        """
        if parent is not None and not issubclass(parent, Field):
            raise TypeError(
                f"{type(self).__name__} can only be bound to a Field subclass."
            )

        self._name = name
        self._parent = parent
        return self

    def is_bound(self) -> bool:
        """Return True if the field is bound to a parent class."""
        if self._parent is None:
            return False
        return issubclass(self._parent, Field) and self._name is not None

    @raiseFieldError
    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]) -> _T:
        """
        Ensure the value meets field requirements and validation criteria.

        Override/extend this method to add custom validation logic.
        """
        field_name = self.get_name()
        if self.is_null(value):
            if not self.allow_null:
                raise FieldError(
                    f"'{field_name}' is not nullable but got null value '{value}'."
                )
            return None

        casted_value = self.cast_to_type(value)
        if self.is_blank(casted_value):
            if not self.allow_blank:
                raise FieldError(
                    f"'{field_name}' cannot be blank but got blank value '{casted_value}'."
                )

        if not self.check_type(casted_value):
            raise FieldError(
                f"'{field_name}' must be of type/form '{self._repr_type(self.get_type())}', not '{type(casted_value).__name__}'."
            )

        self.run_validators(casted_value, instance)
        return casted_value

    def __delete__(self, instance: "_Field"):
        try:
            instance.__values__.pop(self.get_name())
        except (KeyError, FieldError):
            # Ignore if the field value is not set
            # or has not been bound to a parent class
            pass

    # Allow generic typing checking for fields.
    def __class_getitem__(cls, *args, **kwargs):
        return cls

    def cast_to_type(self, value: typing.Any) -> _T:
        """
        Cast the value to the field's specified type, if necessary.

        Converts the field's value to the specified type before it is set on the instance.
        """
        field_type = self.get_type()
        if issubclass(field_type, undefined) or isinstance(value, field_type):
            # If the value is a field, use a copy of the field to avoid shared state.
            if isinstance(value, Field):
                return copy.deepcopy(value)
            return value

        return field_type(value)

    def is_blank(self, value: _T) -> bool:
        """
        Return True if the value is blank, else False.
        """
        if self._lower_if_string(value) in [
            *type(self).default_blank_values,
            *type(self).blank_values,
        ]:
            return True
        return False

    def is_null(self, value: typing.Any) -> bool:
        """
        Return True if the value is null, else False.
        """
        if self._lower_if_string(value) in [
            *type(self).default_null_values,
            *type(self).null_values,
        ]:
            return True
        return False

    def run_validators(self, value: _T, instance: "_Field"):
        """Run all field validators on the provided value."""
        for validator in self.validators:
            if getattr(validator, "requires_instance", False):
                validator(value, instance)
            else:
                validator(value)
        return

    def to_json(self, instance: "_Field") -> typing.Any:
        """
        Return a JSON serializable representation of the field's value on the instance.
        """
        field_name = self.get_name()
        value = getattr(instance, field_name)
        if isinstance(value, Field):
            value = value.to_json(self)

        try:
            return json.loads(json.dumps(value))
        except (TypeError, ValueError) as exc:
            raise FieldError(
                f"Failed to serialize '{type(instance).__name__}.{field_name}' to JSON. "
                "Consider implementing a custom json method or using a supported type."
            ) from exc

    @staticmethod
    def _repr_type(_type: typing.Type) -> str:
        """Return a string representation of the field type."""
        if isinstance(_type, typing._SpecialForm):
            return _type._name

        if is_generic_type(_type):
            return f"{_type.__origin__.__name__}[{' | '.join([Field._repr_type(arg) for arg in typing.get_args(_type)])}]"

        if is_iterable(_type):
            return " | ".join([Field._repr_type(arg) for arg in _type])
        return _type.__name__

    @staticmethod
    def _lower_if_string(value: _R) -> _R:
        if isinstance(value, str):
            return value.lower()
        return value

    NO_DEEPCOPY_ARGS: typing.Tuple[int] = ()
    """
    Indices of arguments that should not be deepcopied when copying the field.

    This is useful for arguments that are immutable or should not be copied to avoid shared state.
    """
    NO_DEEPCOPY_KWARGS: typing.Tuple[str] = ("validators", "regex")
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
        field_copy.__values__ = merge_dicts(
            field_copy.__values__,
            copy.deepcopy(self.__values__, memo),
        )

        if self.is_bound():
            field_copy.bind(self._parent, self._name)
        return field_copy


_Field = typing.TypeVar("_Field", bound=Field, covariant=True)


class FieldInitKwargs(typing.TypedDict):
    """Possible keyword arguments for initializing a field."""

    alias: typing.Optional[str]
    """Optional string for alternative field naming."""
    allow_null: bool
    """If True, permits the field to be set to None."""
    allow_blank: bool
    """If True, permits the field to be set to a blank value."""
    required: bool
    """If True, the field must be explicitly provided."""
    validators: typing.Optional[typing.Iterable[FieldValidator[_T, _Field]]]
    """A list of validation functions to apply to the field's value."""
    default: typing.Union[_T, DefaultFactory, typing.Type[empty]]
    """A default value for the field to be used if no value is set."""
    onsetvalue: typing.Optional[typing.Callable[[typing.Any], typing.Any]]
    """
    Callable to run on the value before setting it. 
    
    Use this to modify the value before it is validated and set on the instance.
    """


class AnyField(Field[typing.Any]):
    """Field for handling values of any type."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        kwargs.setdefault("allow_null", True)
        super().__init__(_type=undefined, **kwargs)


class BooleanField(Field[bool]):
    """Field for handling boolean values."""

    TRUTHY_VALUES = (
        True,
        1,
        "1",
        "true",
        "yes",
    )
    FALSY_VALUES = (
        False,
        0,
        "0",
        "false",
        "no",
        "nil",
        "null",
        "none",
    )

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        kwargs.setdefault("allow_null", True)
        super().__init__(_type=bool, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if self._lower_if_string(value) in self.TRUTHY_VALUES:
            return True
        if self._lower_if_string(value) in self.FALSY_VALUES:
            return False
        return bool(value)


class StringField(Field[str]):
    """Field for handling string values."""

    DEFAULT_MAX_LENGTH: typing.Optional[int] = None
    """Default maximum length of values."""

    def __init__(
        self,
        *,
        max_length: typing.Optional[int] = None,
        trim_whitespaces: bool = True,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param max_length: The maximum length allowed for the field's value.
        :param trim_whitespaces: If True, leading and trailing whitespaces will be removed.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(_type=str, **kwargs)
        self.max_length = max_length or type(self).DEFAULT_MAX_LENGTH
        self.trim_whitespaces = trim_whitespaces

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]) -> str:
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        if self.max_length is not None and len(validated_value) > self.max_length:
            raise FieldError(
                f"'{self.get_name()}' must be at most {self.max_length} characters long."
            )
        return validated_value

    def cast_to_type(self, value: typing.Any):
        if self.trim_whitespaces and isinstance(value, str):
            return value.strip()
        return str(value)


class MinMaxValueMixin(typing.Generic[_T]):
    def __init__(
        self,
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
        super().__init__(**kwargs)
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("min_value cannot be greater than max_value")
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]) -> _T:
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        field_name = self.get_name()
        if self.min_value is not None and validated_value < self.min_value:
            raise FieldError(
                f"'{field_name}' cannot be less than '{self.min_value}' but '{validated_value}' was provided."
            )
        if self.max_value is not None and validated_value > self.max_value:
            raise FieldError(
                f"'{field_name}' cannot be greater than '{self.max_value}' but '{validated_value}' was provided."
            )
        return validated_value


class FloatField(MinMaxValueMixin, Field[float]):
    """Field for handling float values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        kwargs["allow_blank"] = False  # Floats cannot be blank
        super().__init__(_type=float, **kwargs)


class IntegerField(MinMaxValueMixin, Field[int]):
    """Field for handling integer values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        kwargs["allow_blank"] = False  # Integers cannot be blank
        super().__init__(_type=int, **kwargs)


class DictField(Field[typing.Dict]):
    """Field for handling dictionary values."""

    blank_values = [
        {},
    ]

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        super().__init__(dict, **kwargs)


class UUIDField(Field[uuid.UUID]):
    """Field for handling UUID values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        super().__init__(_type=uuid.UUID, **kwargs)

    def cast_to_type(self, value: typing.Any):
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)

    def to_json(self, instance: "_Field") -> str:
        value: uuid.UUID = getattr(instance, self.get_name())
        return str(value)


class BaseListField(Field[_T]):
    """Base class for list/iterable fields with optional validation of list elements."""

    def __init__(
        self,
        _type: typing.Type[_T],
        child: typing.Optional[Field[_V]] = None,
        *,
        size: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param _type: The expected list/iterable type for the field.
        :param child: Optional field for validating elements in the field's value.
        :param size: Optional size constraint for the list/iterable.
        """
        if not is_iterable_type(_type, exclude=(str, bytes)):
            raise TypeError(
                "Specified type must be an iterable type; excluding str or bytes."
            )
        super().__init__(_type=_type, **kwargs)

        if not isinstance(child, Field):
            raise TypeError("child must be a Field")

        # Copy the child field to avoid shared state
        self.child = copy.deepcopy(child) if child else AnyField()
        # Bind the child field to the parent field
        self.child.bind(type(self), "child")
        self.size = size

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        validated_value = super().validate(value, instance)
        if value is None:
            return None

        if self.size is not None and len(validated_value) != self.size:
            raise FieldError(
                f"'{self.get_name()}' must contain exactly {self.size} items."
            )
        return [self.child.validate(item, instance) for item in validated_value]

    def to_json(self, instance: "_Field"):
        value: typing.List[_T] = getattr(instance, self.get_name())
        return [
            (item.to_json(self) if isinstance(item, Field) else item) for item in value
        ]


class ListField(BaseListField[typing.List]):
    """Field for lists, with optional validation of list elements through the `child` field."""

    blank_values = [
        [],
    ]

    def __init__(
        self,
        child: typing.Optional[Field[_V]] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        super().__init__(_type=list, child=child, **kwargs)


class SetField(BaseListField[typing.Set]):
    """Field for sets, with optional validation of set elements through the `child` field."""

    blank_values = [
        set(),
    ]

    def __init__(
        self,
        child: typing.Optional[Field[_V]] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        super().__init__(_type=set, child=child, **kwargs)

    def validate(
        self, value: typing.Any, instance: typing.Optional["_Field"]
    ) -> typing.Set[_V]:
        if value is None:
            return None

        return set(super().validate(value, instance))


class TupleField(BaseListField[typing.Tuple]):
    """Field for tuples, with optional validation of tuple elements through the `child` field."""

    blank_values = [
        tuple(),
    ]

    def __init__(
        self,
        child: Field[_V] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        super().__init__(_type=tuple, child=child, **kwargs)

    def validate(
        self, value: typing.Any, instance: typing.Optional["_Field"]
    ) -> typing.Tuple[_V]:
        if value is None:
            return None

        return tuple(super().validate(value, instance))


class DecimalField(Field[decimal.Decimal]):
    """Field for handling decimal values."""

    def __init__(
        self,
        dp: typing.Optional[int] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param dp: The number of decimal places to round the field's value to.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(_type=decimal.Decimal, **kwargs)
        self.dp = None if dp is None else int(dp)

    def cast_to_type(self, value):
        value = decimal.Decimal(value)
        if self.dp:
            return value.quantize(decimal.Decimal(f"0.{'0'*(self.dp - 1)}1"))
        return value

    def to_json(self, instance: _Field) -> str:
        value: decimal.Decimal = getattr(instance, self.get_name())
        return str(value)


class EmailField(StringField):
    """Field for handling email addresses."""

    EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]) -> str:
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        if not re.match(type(self).EMAIL_REGEX, validated_value):
            raise FieldError(f"'{self.get_name()}' must be a valid email address.")
        return validated_value


class URLField(Field[Url]):
    """Field for handling URL values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        super().__init__(_type=(str, Url), **kwargs)

    def cast_to_type(self, value: typing.Any):
        if isinstance(value, Url):
            return value
        return parse_url(value)


class ChoiceMixin(typing.Generic[_T]):
    """Mixin for choice fields."""

    def __init__(self, choices: typing.List[_T], **kwargs):
        super().__init__(**kwargs)

        if len(choices) < 2:
            raise ValueError("Two or more choices are required")
        self.choices = choices

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        value = super().validate(value, instance)
        if value not in self.choices:
            raise FieldError(f"'{self.get_name()}' must be one of {self.choices}.")
        return value


class ChoiceField(ChoiceMixin, AnyField):
    """Field for with predefined choices for values."""

    pass


class StringChoiceField(ChoiceMixin, StringField):
    """String field with predefined choices for values."""

    pass


class IntegerChoiceField(ChoiceMixin, IntegerField):
    """Integer field with predefined choices for values."""

    pass


class FloatChoiceField(ChoiceMixin, FloatField):
    """Float field with predefined choices for values."""

    pass


class TypedChoiceField(ChoiceMixin, Field[_T]):
    """Choice field with defined type enforcement."""

    def __init__(
        self,
        _type: typing.Type[_T],
        choices: typing.List[_T],
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param _type: The expected type for choice field's values.
        :param choices: A list of valid choices for the field.
        """
        super().__init__(_type=_type, choices=choices, **kwargs)


class JSONField(AnyField):
    """Field for handling JSON data."""

    def cast_to_type(self, value: typing.Any) -> typing.Any:
        if isinstance(value, str):
            return json.loads(value)
        return json.loads(json.dumps(value))


class HexColorField(StringField):
    """Field for handling hex color values."""

    HEX_COLOR_REGEX = r"^#(?:[0-9a-fA-F]{3,4}){1,2}$"
    DEFAULT_MAX_LENGTH = 9

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        if not re.match(type(self).HEX_COLOR_REGEX, validated_value):
            raise FieldError(f"'{self.get_name()}' must be a valid hex color code.")
        return validated_value


class RGBColorField(StringField):
    """Field for handling RGB color values."""

    RGB_COLOR_REGEX = r"^rgb[a]?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(\d{1,3})\s*)?\)$"
    DEFAULT_MAX_LENGTH = 38

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        validated_value = validated_value.lower().strip()
        if not re.match(type(self).RGB_COLOR_REGEX, validated_value):
            raise FieldError(f"'{self.get_name()}' must be a valid RGB color code.")
        return validated_value


class HSLColorField(StringField):
    """Field for handling HSL color values."""

    HSL_COLOR_REGEX = r"^hsl[a]?\(\s*(\d{1,3})\s*,\s*(\d{1,3})%?\s*,\s*(\d{1,3})%?\s*(?:,\s*(\d{1,3})\s*)?\)$"
    DEFAULT_MAX_LENGTH = 40

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        validated_value = validated_value.lower().strip()
        if not re.match(type(self).HSL_COLOR_REGEX, validated_value):
            raise FieldError(f"'{self.get_name()}' must be a valid HSL color code.")
        return validated_value


class IPAddressField(Field[typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]):
    """Field for hanling IP addresses."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        super().__init__(
            _type=(str, ipaddress.IPv4Address, ipaddress.IPv6Address), **kwargs
        )

    def cast_to_type(self, value: typing.Any):
        return ipaddress.ip_address(value)

    def to_json(self, instance: "_Field") -> str:
        """Return a JSON representation of the field's value."""
        value: typing.Union[ipaddress.IPv4Address, ipaddress.IPv6Address] = getattr(
            instance, self.get_name()
        )
        return value.exploded


class SlugField(StringField):
    """Field for URL-friendly strings."""

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        if not re.match(r"^[a-zA-Z0-9_-]+$", validated_value):
            raise FieldError(f"'{self.get_name()}' must be a valid slug.")
        return validated_value


# These next datetime fields are implemented with dependencies on Django.
# Warning messages are displayed when the fields are initialized
# without the required dependencies installed.
# This is to allows for other fields in this module to be useable even
# without the dependencies for these fields being installed.
class DateField(Field[datetime.date]):
    """Field for handling date values."""

    DEFAULT_OUTPUT_FORMAT: str = "%Y-%m-%d"

    def __init__(
        self,
        input_format: typing.Optional[str] = None,
        output_format: typing.Optional[str] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param input_format: The expected input format for the date value.
            If not provided, the field will attempt to parse the date value
            itself.
        :param output_format: The preferred output format for the date value.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(_type=(str, datetime.date), **kwargs)
        self.input_format = input_format
        self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT

    def parse_date(self, value: str) -> datetime.date:
        """
        Parse the date string into a date object.

        Override this method to implement custom date parsing logic.
        """
        if self.input_format:
            return datetime.datetime.strptime(value, self.input_format).date()

        deps_required({"dateutil": "python-dateutil"})
        from dateutil.parser import parse

        parsed_date = parse(value).date()
        if parsed_date is None:
            raise ValueError(f"Invalid date value - {value}")
        return parsed_date

    def cast_to_type(self, value: typing.Any) -> datetime.date:
        if isinstance(value, datetime.date):
            return value

        if not isinstance(value, str):
            raise ValueError(f"Invalid date value - {value}")

        return self.parse_date(value)

    def to_json(self, instance: "_Field") -> str:
        value: datetime.date = getattr(instance, self.get_name())
        return value.strftime(self.output_format)


class TimeField(Field[datetime.time]):
    """Field for handling time values."""

    DEFAULT_OUTPUT_FORMAT: str = "%H:%M:%S.%s"

    def __init__(
        self,
        input_format: typing.Optional[str] = None,
        output_format: typing.Optional[str] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param input_format: The expected input format for the time value.
            If not provided, the field will attempt to parse the time value
            itself.
        :param output_format: The preferred output format for the time value.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(_type=(str, datetime.time), **kwargs)
        self.input_format = input_format
        self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT

    def parse_time(self, value: str) -> datetime.time:
        """
        Parse the time string into a time object.

        Override this method to implement custom time parsing logic.
        """
        if self.input_format:
            return datetime.datetime.strptime(value, self.input_format).time()

        deps_required({"dateutil": "python-dateutil"})
        from dateutil.parser import parse

        parsed_time = parse(value).time()
        if parsed_time is None:
            raise ValueError(f"Invalid time value - {value}")
        return parsed_time

    def cast_to_type(self, value: typing.Any) -> datetime.time:
        if isinstance(value, datetime.time):
            return value

        if not isinstance(value, str):
            raise ValueError(f"Invalid time value - {value}")

        return self.parse_time(value)

    def to_json(self, instance: "_Field") -> str:
        value: datetime.time = getattr(instance, self.get_name())
        return value.strftime(self.output_format)


class DurationField(Field[datetime.timedelta]):
    """Field for handling duration values."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        super().__init__(_type=(str, datetime.timedelta), **kwargs)

    def parse_duration(self, value: str) -> datetime.timedelta:
        """
        Parse the duration string into a timedelta object.

        Override this method to implement custom duration parsing logic.
        """
        parsed_duration = parse_duration(value)
        if parsed_duration is None:
            raise ValueError(f"Invalid duration value - {value}")
        return parsed_duration

    def cast_to_type(self, value: typing.Any) -> datetime.timedelta:
        if isinstance(value, datetime.timedelta):
            return value

        if not isinstance(value, str):
            raise ValueError(f"Invalid duration value - {value}")

        return self.parse_duration(value)

    def to_json(self, instance: "_Field") -> str:
        value: datetime.timedelta = getattr(instance, self.get_name())
        return str(value)


TimeDeltaField = DurationField


class DateTimeField(Field[datetime.datetime]):
    """Field for handling datetime values."""

    DEFAULT_OUTPUT_FORMAT = "%Y-%m-%d %H:%M:%S%z"

    def __init__(
        self,
        input_format: typing.Optional[str] = None,
        output_format: typing.Optional[str] = None,
        tz: typing.Optional[datetime.tzinfo] = None,
        **kwargs: Unpack[FieldInitKwargs],
    ):
        """
        Initialize the field.

        :param input_format: The expected input format for the datetime value.
            If not provided, the field will attempt to parse the datetime value
            itself.
        :param output_format: The preferred output format for the datetime value.
        :param tz: The timezone to use for the datetime value. If this set,
            the datetime value will be represented in this timezone.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(_type=(str, datetime.datetime), **kwargs)
        self.input_format = input_format
        self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT
        self.tz = tz

    def parse_datetime(self, value: str) -> datetime.datetime:
        """
        Parse the datetime string into a datetime object.

        Override this method to implement custom datetime parsing logic.
        """
        if self.input_format:
            return datetime.datetime.strptime(value, self.input_format)

        deps_required({"dateutil": "python-dateutil"})
        from dateutil.parser import parse

        parsed_datetime = parse(value)
        if parsed_datetime is None:
            raise ValueError(f"Invalid datetime value - {value}")
        return parsed_datetime

    def cast_to_type(self, value: typing.Any) -> datetime.datetime:
        if isinstance(value, datetime.datetime):
            parsed_datetime = value
        else:
            if not isinstance(value, str):
                raise FieldError(f"Invalid datetime value - {value}")
            parsed_datetime = self.parse_datetime(value)

        if self.tz:
            if parsed_datetime.tzinfo:
                parsed_datetime = parsed_datetime.astimezone(self.tz)
            else:
                parsed_datetime = parsed_datetime.replace(tzinfo=self.tz)
        return parsed_datetime

    def to_json(self, instance: "_Field") -> str:
        value: datetime.datetime = getattr(instance, self.get_name())
        return value.strftime(self.output_format)


class BytesField(Field[bytes]):
    """Field for handling byte values."""

    def __init__(self, str_encoding: str = "UTF-8", **kwargs: Unpack[FieldInitKwargs]):
        """
        Initialize the field.

        :param str_encoding: The encoding to use when encoding/decoding byte strings.
        :param kwargs: Additional keyword arguments for the field.
        """
        super().__init__(_type=(str, bytes), **kwargs)
        self.str_encoding = str_encoding

    def cast_to_type(self, value: typing.Any):
        if isinstance(value, bytes):
            return value

        if isinstance(value, str):
            try:
                return base64.b64decode(value.encode(encoding=self.str_encoding))
            except (ValueError, TypeError) as exc:
                raise FieldError("Invalid base64 string for bytes") from exc
        return value

    def to_json(self, instance: "_Field") -> str:
        """Return a JSON representation of the field's value."""
        value: bytes = getattr(instance, self.get_name())
        return base64.b64encode(value).decode(encoding=self.str_encoding)


class IOField(Field[typing.IO]):
    """Field for handling file-like I/O objects."""

    def __init__(self, **kwargs: Unpack[FieldInitKwargs]):
        super().__init__(_type=io.IOBase, **kwargs)

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        """Validate that the value is a file-like object."""
        validated_value = super().validate(value, instance)
        if validated_value is None:
            return None

        if not (
            hasattr(validated_value, "read")
            and callable(getattr(validated_value, "read"))
            and hasattr(validated_value, "write")
            and callable(getattr(validated_value, "write"))
        ):
            raise FieldError("The provided object does not support IO operations")
        return validated_value

    def to_json(self, instance: "_Field"):
        raise FieldError(f"{type(self).__name__} does not support JSON serialization.")


class FileField(IOField):
    """Field for handling files"""

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
        super().__init__(**kwargs)
        self.max_size = max_size
        self.allowed_types = allowed_types or []

    def validate(self, value: typing.Any, instance: typing.Optional["_Field"]):
        """Validate the file object, checking size and type constraints."""
        file_obj = super().validate(value, instance)
        if file_obj is None:
            return None

        if self.max_size is not None:
            file_obj.seek(0, 2)  # Move to end of file to check size
            file_size = file_obj.tell()
            file_obj.seek(0)  # Reset file pointer to the beginning
            if file_size > self.max_size:
                raise FieldError(f"File exceeds maximum size of {self.max_size} bytes.")

        if self.allowed_types:
            # Check if the file has an allowed type or extension
            if not self.is_allowed_file_type(file_obj):
                raise FieldError(
                    f"File type not allowed. Allowed types: {self.allowed_types}."
                )

        return file_obj

    def is_allowed_file_type(self, file_obj: typing.IO) -> bool:
        """Check if the file type or extension is allowed."""
        # Example implementation; in a real scenario, you might want to check MIME types
        # or the file extension based on file name or magic numbers.
        file_name = getattr(file_obj, "name", "")
        if not file_name:
            return False
        file_extension = file_name.split(".")[-1].lower()
        if not file_extension:
            return False
        return file_extension in [ext.lower() for ext in self.allowed_types]

    def __delete__(self, instance: "_Field"):
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
            super().__init__(_type=(str, PhoneNumber), **kwargs)
            self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT

        def cast_to_type(self, value: typing.Any):
            if isinstance(value, PhoneNumber):
                return value

            try:
                return parse(value)
            except Exception as exc:
                raise FieldError(f"Invalid phone number - {value}") from exc

        def to_json(self, instance: "_Field"):
            value: PhoneNumber = getattr(instance, self.get_name())
            return format_number(value, self.output_format)

    class PhoneNumberStringField(StringField):
        """Phone number string field"""

        DEFAULT_OUTPUT_FORMAT = PhoneNumberFormat.E164

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
            kwargs.setdefault("max_length", 20)
            super().__init__(**kwargs)
            self.output_format = output_format or type(self).DEFAULT_OUTPUT_FORMAT

        def cast_to_type(self, value: typing.Any):
            return format_number(parse(value), self.output_format)

        def to_json(self, instance: "_Field"):
            # The cast_to_type method already does the formatting
            return self.cast_to_type(getattr(instance, self.get_name()))

except ImportError:
    pass


__all__ = [
    "FieldError",
    "Field",
    "FieldInitKwargs",
    "AnyField",
    "BooleanField",
    "StringField",
    "FloatField",
    "IntegerField",
    "DictField",
    "BaseListField",
    "ListField",
    "SetField",
    "TupleField",
    "DecimalField",
    "EmailField",
    "URLField",
    "ChoiceMixin",
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
    "_Field",
]
