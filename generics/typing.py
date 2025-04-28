import typing
from dataclasses import dataclass
from typing_extensions import ParamSpec


class SupportsRichComparison(typing.Protocol):
    def __lt__(self, other: typing.Any, /) -> bool: ...
    def __le__(self, other: typing.Any, /) -> bool: ...
    def __gt__(self, other: typing.Any, /) -> bool: ...
    def __ge__(self, other: typing.Any, /) -> bool: ...
    def __eq__(self, other: typing.Any, /) -> bool: ...
    def __ne__(self, other: typing.Any, /) -> bool: ...


class SupportsKeysAndGetItem(typing.Protocol):
    def __getitem__(self, name: typing.Any, /) -> typing.Any: ...

    def keys(self) -> typing.Iterable[typing.Any]: ...


class SupportsLen(typing.Protocol):
    def __len__(self) -> int: ...


P = ParamSpec("P")
R = typing.TypeVar("R")

Function = typing.Callable[P, R]
CoroutineFunction = typing.Callable[P, typing.Awaitable[R]]


@dataclass
class _Dataclass:
    pass

DataclassType = type(_Dataclass)
