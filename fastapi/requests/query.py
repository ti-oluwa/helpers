import fastapi
import typing
from annotated_types import Ge, Le


Limit = typing.Annotated[
    int,
    Le(1000),
    Ge(1),
    fastapi.Query(
        description="Maximum number of objects to return",
    ),
]
"""Annotated dependency for a limit query parameter with a value between 1 and 1000"""

Offset = typing.Annotated[
    int,
    Ge(0),
    fastapi.Query(description="Number of objects to skip"),
]
"""Annotated dependency for an offset query parameter with a value of at least 0"""


__all__ = [
    "Limit",
    "Offset",
]
