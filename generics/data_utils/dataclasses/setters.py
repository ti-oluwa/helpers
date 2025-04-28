import typing

from .exceptions import FrozenFieldError

_T = typing.TypeVar("_T")


Setter = typing.Callable[[_T], typing.Union[_T, typing.Any]]


def frozen(value: typing.Any):
    """
    setter function to mark a field as frozen.
    """
    raise FrozenFieldError(f"Cannot modify frozen field with value: {value}")


def pipe(*setters: Setter[_T]) -> Setter[_T]:
    """
    Create a pipeline of setters.

    :param setters: List of setter functions.
    :return: A function that applies the setters in sequence.
    """

    def pipeline(value: _T) -> typing.Union[_T, typing.Any]:
        for setter in setters:
            value = setter(value)
        return value

    return pipeline
