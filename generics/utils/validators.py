import typing
import re

_T = typing.TypeVar("_T")

NONE = object()


def min_length_validator(min_length: int, value: _T = NONE) -> _T:
    """
    Validates the minimum length of a string

    :param value: The value to validate
    :param min_length: The minimum length of the string
    :return: The value if it is valid
    :raises ValueError: If the value is not valid
    """
    if value is NONE:
        return lambda v: min_length_validator(min_length, v)

    if len(value) < min_length:
        raise ValueError(f"Value must be at least {min_length} characters long")
    return value


def max_length_validator(max_length: int, value: _T = NONE) -> _T:
    """
    Validates the maximum length of a string

    :param value: The value to validate
    :param max_length: The maximum length of the string
    :return: The value if it is valid
    :raises ValueError: If the value is not valid
    """
    if value is NONE:
        return lambda v: max_length_validator(max_length, v)

    if len(value) > max_length:
        raise ValueError(f"Value must be at most {max_length} characters long")
    return value


email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$")


def email_validator(value: str) -> str:
    """
    Validates an email address

    :param value: The email address to validate
    :return: The email address if it is valid
    :raises ValueError: If the email address is not valid
    """
    if not email_regex.match(value):
        raise ValueError("Invalid email address")
    return value
