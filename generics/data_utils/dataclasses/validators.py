import inspect
import typing
import operator
import re

from helpers.generics.typing import SupportsRichComparison, SupportsLen
from .exceptions import FieldError


_Validator: typing.TypeAlias = typing.Callable[
    [
        typing.Any,
        typing.Optional[typing.Any],
        typing.Optional[typing.Any],
    ],
    None,
]

Bound = SupportsRichComparison
ComparableValue = SupportsRichComparison
CountableValue = SupportsLen


def is_context_validator(
    validator: _Validator,
) -> bool:
    """Return True if the validator is a context validator."""
    return getattr(validator, "requires_context", False)


class FieldValidator:
    __slots__ = ("func", "requires_context", "message")

    def __init__(
        self,
        func: _Validator,
        *,
        requires_context: bool = False,
        message: typing.Optional[str] = None,
    ):
        self.func = func
        self.requires_context = requires_context
        self.message = message

    @property
    def __doc__(self) -> str:
        return self.func.__doc__

    @property
    def __name__(self):
        return repr(self)

    def __call__(
        self,
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        try:
            if self.requires_context:
                self.func(value, field, instance)
            else:
                self.func(value)
        except (ValueError, TypeError) as exc:
            msg = self.message or str(exc)
            raise FieldError(
                msg.format_map(
                    {
                        "name": field.get_name() if field else "value",
                        "value": value,
                        "field": field,
                    }
                )
            ) from exc

    def __hash__(self) -> int:
        try:
            return hash(self.func)
        except TypeError:
            return hash(id(self.func))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({repr(self.func)})"


def load_validators(
    *validators: _Validator,
) -> typing.Set[FieldValidator]:
    """Load the field validators into preferred internal type."""
    loaded_validators: typing.Set[FieldValidator] = set()
    for validator in validators:
        if isinstance(validator, FieldValidator):
            loaded_validators.add(validator)
            continue

        if not callable(validator):
            raise TypeError(f"Field validator '{validator}' is not callable.")

        loaded_validators.add(
            FieldValidator(validator, requires_context=is_context_validator(validator))
        )
    return loaded_validators


_NUMBER_VALIDATION_FAILURE_MESSAGE = "'{value} {symbol} {bound}' is not True"


def number_validator_factory(
    comparison_func: typing.Callable[[ComparableValue, Bound], bool], symbol: str
):
    def validator_factory(bound: Bound, message: typing.Optional[str] = None):
        global _NUMBER_VALIDATION_FAILURE_MESSAGE

        msg = message or _NUMBER_VALIDATION_FAILURE_MESSAGE

        def validator(
            value: typing.Union[ComparableValue, typing.Any],
            field: typing.Optional[typing.Any] = None,
            instance: typing.Optional[typing.Any] = None,
        ):
            nonlocal msg

            if comparison_func(value, bound):
                return

            name = field.get_name() if field else "value"
            raise ValueError(
                msg.format_map(
                    {
                        "value": value,
                        "symbol": symbol,
                        "bound": bound,
                        "name": name,
                        "field": field,
                    }
                ),
                value,
                bound,
                symbol,
            )

        validator.__name__ = f"value_{symbol}_{bound}"
        return FieldValidator(validator, requires_context=True)

    validator_factory.__name__ = f"value_{symbol}_validator_factory"
    return validator_factory


gte = number_validator_factory(operator.ge, ">=")
lte = number_validator_factory(operator.le, "<=")
gt = number_validator_factory(operator.gt, ">")
lt = number_validator_factory(operator.lt, "<")
eq = number_validator_factory(operator.eq, "=")


def number_range(
    min_val: SupportsRichComparison,
    max_val: SupportsRichComparison,
    message: str = None,
):
    """
    Number range validator.

    :param min_val: Minimum allowed value
    :param max_val: Maximum allowed value
    :param message: Error message template
    """
    msg = message or "'{name}' must be between {min} and {max}"

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        if value < min_val or value > max_val:
            name = field.get_name() if field else "value"
            raise ValueError(msg.format(name=name, min=min_val, max=max_val))

    validator.__name__ = f"value_between_{min_val}_{max_val}"
    return FieldValidator(validator, requires_context=True)


_LENGTH_VALIDATION_FAILURE_MESSAGE = (
    "'len({name}) {symbol} {bound}' is not True, got {length}"
)


def length_validator_factory(
    comparison_func: typing.Callable[[CountableValue, Bound], bool], symbol: str
):
    def validator_factory(bound: Bound, message: typing.Optional[str] = None):
        global _LENGTH_VALIDATION_FAILURE_MESSAGE

        msg = message or _LENGTH_VALIDATION_FAILURE_MESSAGE

        def validator(
            value: typing.Union[CountableValue, typing.Any],
            field: typing.Optional[typing.Any] = None,
            instance: typing.Optional[typing.Any] = None,
        ):
            nonlocal msg

            if comparison_func(len(value), bound):
                return
            name = field.get_name() if field else "value"
            length = len(value)
            raise ValueError(
                msg.format_map(
                    {
                        "name": name,
                        "field": name,
                        "symbol": symbol,
                        "bound": bound,
                        "value": value,
                        "length": length,
                    }
                ),
                value,
                bound,
                symbol,
                length,
            )

        validator.__name__ = f"value_length_{symbol}_{bound}"
        return FieldValidator(validator, requires_context=True)

    validator_factory.__name__ = f"value_length_{symbol}_validator_factory"
    return validator_factory


min_len = length_validator_factory(operator.ge, ">=")
max_len = length_validator_factory(operator.le, "<=")
len_ = length_validator_factory(operator.eq, "=")


_NO_MATCH_MESSAGE = "'{name}' must match pattern {pattern!r} ({value!r} doesn't)"


def pattern(
    regex: typing.Union[re.Pattern, typing.AnyStr],
    flags: re.RegexFlag = 0,
    func: typing.Optional[typing.Callable] = None,
    message: typing.Optional[str] = None,
):
    r"""
    A validator that raises `ValueError` if the initializer is called with a
    string that doesn't match *regex*.

    Args:
        regex (str, re.Pattern):
            A regex string or precompiled pattern to match against

        flags (int):
            Flags that will be passed to the underlying re function (default 0)

        func (typing.Callable):
            Which underlying `re` function to call. Valid options are
            `re.fullmatch`, `re.search`, and `re.match`; the default `None`
            means `re.fullmatch`. For performance reasons, the pattern is
            always precompiled using `re.compile`.
    """
    global _NO_MATCH_MESSAGE

    valid_funcs = (re.fullmatch, None, re.search, re.match)
    if func not in valid_funcs:
        msg = "'func' must be one of {}.".format(
            ", ".join(sorted((e and e.__name__) or "None" for e in set(valid_funcs)))
        )
        raise ValueError(msg)

    if isinstance(regex, re.Pattern):
        if flags:
            msg = "'flags' can only be used with a string pattern; pass flags to re.compile() instead"
            raise TypeError(msg)
        pattern = regex
    else:
        pattern = re.compile(regex, flags)

    if func is re.match:
        match_func = pattern.match
    elif func is re.search:
        match_func = pattern.search
    else:
        match_func = pattern.fullmatch

    msg = message or _NO_MATCH_MESSAGE

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        nonlocal msg

        if not match_func(value):
            name = field.get_name() if field else "value"
            raise ValueError(
                msg.format_map(
                    {
                        "name": name,
                        "pattern": pattern.pattern,
                        "value": value,
                    }
                ),
                pattern,
                value,
            )

    validator.__name__ = f"validate_pattern_{pattern.pattern!r}"
    return FieldValidator(validator, requires_context=True)


_INSTANCE_CHECK_FAILURE_MESSAGE = "Value must be an instance of {cls!r}"


def instance_of(
    cls: typing.Union[typing.Type, typing.Tuple[typing.Type, ...]],
    message: typing.Optional[str] = None,
):
    """
    A validator that raises `ValueError` if the initializer is called with a
    value that is not an instance of *cls*.

    Args:
        cls (type):
            The type to check against.

    """
    global _INSTANCE_CHECK_FAILURE_MESSAGE

    msg = message or _INSTANCE_CHECK_FAILURE_MESSAGE

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        nonlocal msg

        if not isinstance(value, cls):
            name = field.get_name() if field else "value"
            raise ValueError(
                msg.format_map(
                    {"cls": cls, "value": value, "name": name, "field": field}
                ),
                value,
                cls,
            )

    validator.__name__ = f"isinstance_of_{cls!r}"
    return FieldValidator(validator, requires_context=True)


_SUBCLASS_CHECK_FAILURE_MESSAGE = "Value must be a subclass of {cls!r}"


def subclass_of(
    cls: typing.Union[typing.Type, typing.Tuple[typing.Type, ...]],
    message: typing.Optional[str] = None,
):
    """
    A validator that raises `ValueError` if the initializer is called with a
    value that is not a subclass of *cls*.

    Args:
        cls (type):
            The type to check against.

    """
    global _SUBCLASS_CHECK_FAILURE_MESSAGE

    msg = message or _SUBCLASS_CHECK_FAILURE_MESSAGE

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        nonlocal msg

        if not (inspect.isclass(value) and issubclass(value, cls)):
            name = field.get_name() if field else "value"
            raise ValueError(
                msg.format_map(
                    {"cls": cls, "value": value, "name": name, "field": field}
                ),
                value,
                cls,
            )

    validator.__name__ = f"issubclass_of_{cls!r}"
    return FieldValidator(validator, requires_context=True)


def optional(validator: _Validator):
    """
    A validator that allows `None` as a valid value for the field.

    Args:
        validator (typing.Callable):
            The validator to apply to the field, if the field is not `None`.

    """
    _validator = load_validators(validator).pop()

    def optional_validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        if field and field.is_null(value):
            return
        if value is None:
            return
        return _validator(value, field, instance)

    optional_validator.__name__ = f"optional({validator.__name__})"
    return FieldValidator(optional_validator, requires_context=True)


_IN_CHECK_FAILURE_MESSAGE = "Value must be in {choices!r}"


def in_(choices: typing.Iterable, message: typing.Optional[str] = None):
    """
    A validator that raises `ValueError` if the initializer is called with a
    value that is not in *choices*.

    Args:
        choices (Iterable):
            The iterable to check against.

    """
    global _IN_CHECK_FAILURE_MESSAGE

    msg = message or _IN_CHECK_FAILURE_MESSAGE

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        nonlocal msg

        if value not in choices:
            name = field.get_name() if field else "value"
            raise ValueError(
                msg.format_map(
                    {"choices": choices, "value": value, "name": name, "field": field}
                ),
                value,
                choices,
            )

    validator.__name__ = f"member_of_{choices!r}"
    return FieldValidator(validator, requires_context=True)


_NEGATION_CHECK_FAILURE_MESSAGE = "Value must not validate {validator!r}"


def not_(validator: typing.Callable, message: typing.Optional[str] = None):
    """
    A validator that raises `ValueError` if the initializer is called with a
    value that validates against *validator*.

    Args:
        validator (typing.Callable):
            The validator to check against.

    """
    global _NEGATION_CHECK_FAILURE_MESSAGE

    msg = message or _NEGATION_CHECK_FAILURE_MESSAGE
    _validator = load_validators(validator).pop()

    def negative_validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        nonlocal msg

        try:
            _validator(value, field, instance)
        except ValueError:
            return
        name = field.get_name() if field else "value"
        raise ValueError(
            msg.format_map(
                {"validator": validator, "value": value, "name": name, "field": field}
            ),
            value,
            validator,
        )

    negative_validator.__name__ = f"negate({validator.__name__})"
    return FieldValidator(negative_validator, requires_context=True)


def and_(*validators: typing.Callable):
    """
    A validator that raises `ValueError` if the initializer is called with a
    value that does not validate against all of *validators*.

    Args:
        *validators (typing.Callable):
            The validators to check against.

    """

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        for validator in validators:
            validator(value, field, instance)
        return

    validator.__name__ = f"conjunction({[v.__name__ for v in validators]})"
    return FieldValidator(validator, requires_context=True)


_DISJUNCTION_CHECK_FAILURE_MESSAGE = (
    "Value must validate at least one of {validators!r}"
)


def or_(*validators: typing.Callable, message: typing.Optional[str] = None):
    """
    A validator that raises `ValueError` if the initializer is called with a
    value that does not validate against any of *validators*.

    Args:
        *validators (typing.Callable):
            The validators to check against.

    """
    global _DISJUNCTION_CHECK_FAILURE_MESSAGE

    msg = message or _DISJUNCTION_CHECK_FAILURE_MESSAGE

    def validator(
        value: typing.Any,
        field: typing.Optional[typing.Any] = None,
        instance: typing.Optional[typing.Any] = None,
    ):
        nonlocal msg

        for validator in validators:
            try:
                validator(value, field, instance)
                return
            except ValueError:
                continue
        name = field.get_name() if field else "value"
        raise ValueError(
            msg.format_map(
                {
                    "validators": [v.__name__ for v in validators],
                    "value": value,
                    "name": name,
                    "field": field,
                }
            ),
            value,
            [v.__name__ for v in validators],
        )

    validator.__name__ = f"disjunction({[v.__name__ for v in validators]})"
    return validator


def _is_callable(
    value: typing.Any,
    field: typing.Optional[typing.Any] = None,
    instance: typing.Optional[typing.Any] = None,
):
    if not callable(value):
        name = field.get_name() if field else "value"
        raise ValueError(
            f"'{name}' must be callable",
            value,
        )


is_callable = FieldValidator(_is_callable, requires_context=True)
