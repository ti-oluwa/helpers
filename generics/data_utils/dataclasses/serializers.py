import typing
from collections import defaultdict

from .exceptions import SerializationError

_Serializer: typing.TypeAlias = typing.Callable[..., typing.Any]


def _unsupported_serializer(*args, **kwargs) -> None:
    """Raise an error for unsupported serialization."""
    raise SerializationError(
        "Unsupported serialization format. Register a serializer for this format."
    )


def _unsupported_serializer_factory():
    """Return a function that raises an error for unsupported serialization."""
    return _unsupported_serializer


class Serializer(typing.NamedTuple):
    """
    Serializer class to handle different serialization formats.

    :param serializer_map: A dictionary mapping format names to their respective serializer functions.
    """

    serializer_map: typing.DefaultDict[str, _Serializer] = defaultdict(
        _unsupported_serializer_factory
    )

    def __call__(self, fmt: str, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        """
        Serialize data using the specified format.

        :param fmt: The format to serialize to (e.g., 'json', 'xml').
        :param args: Positional arguments to pass to the format's serializer.
        :param kwargs: Keyword arguments to pass to the format's serializer.
        :return: Serialized data in the specified format.
        """
        return self.serializer_map[fmt](*args, **kwargs)
