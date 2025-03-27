import fastapi
import pydantic
import typing
import sqlalchemy as sa
from annotated_types import Ge, Le

from helpers.fastapi.sqlalchemy.models import ModelBase


@typing.final
class QueryParamNotSet(pydantic.BaseModel):
    """Sentinel class which represent an unset query parameter"""

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "QueryParamNotSet"

    def __class_getitem__(cls, *args):  # type: ignore
        return None

    def __copy__(self):
        return self

    def __deepcopy__(
        self, memo: typing.Optional[typing.Dict[int, typing.Any]] = None
    ) -> "QueryParamNotSet":
        return self


ParamNotSet = QueryParamNotSet()


def clean_params(**params: typing.Any) -> typing.Dict[str, typing.Any]:
    """
    Exclude query parameters that are not set, i.e. instances of `QueryParamNotSet`
    """
    return {
        key: value
        for key, value in params.items()
        if isinstance(value, QueryParamNotSet) is False
    }


Limit: typing.TypeAlias = typing.Annotated[
    pydantic.PositiveInt,
    Le(1000),
    Ge(1),
    fastapi.Query(
        description="Maximum number of objects to return",
    ),
]
"""Annotated dependency for a limit query parameter with a value between 1 and 1000"""

Offset: typing.TypeAlias = typing.Annotated[
    int,
    Ge(0),
    fastapi.Query(description="Number of objects to skip"),
]
"""Annotated dependency for an offset query parameter with a value of at least 0"""

_T = typing.TypeVar(
    "_T",
    bound=ModelBase,
    covariant=True,
)

OrderingExpressions: typing.TypeAlias = typing.List[sa.UnaryExpression[_T]]
"""Type alias for a list of SQLAlchemy ordering expressions"""


def ordering_query_parser_factory(
    ordered: typing.Type[_T],
    *,
    allowed_columns: typing.Optional[typing.Set[str]] = None,
) -> typing.Callable[
    [str],
    typing.Awaitable[typing.Union[OrderingExpressions[_T], QueryParamNotSet]],
]:
    """
    Dependency factory to create an ordering query parameter parser

    :param ordered: The SQLAlchemy model class to order on.
    :param allowed_columns: Allowed columns for ordering on the endpoints model
    :return: Dependency function to parse ordering query parameter
    """
    if allowed_columns is not None and not allowed_columns:
        raise ValueError("allowed_columns must not be an empty set")

    if allowed_columns is None:
        allowed_columns = {column.name for column in ordered.__table__.columns}  # type: ignore
    else:
        table_columns = ordered.__table__.columns  # type: ignore
        for column in allowed_columns:
            if column not in table_columns:
                raise ValueError(
                    f"Column {column} not found in ordered model '{ordered.__name__}'"
                )

    async def _query_parser(
        ordering: typing.Annotated[
            typing.Optional[str],
            fastapi.Query(
                description=f"Ordering on '{ordered.__name__}'. Prefix with '-' for descending order.",
            ),
        ] = None,
    ) -> typing.Union[OrderingExpressions[_T], QueryParamNotSet]:
        if ordering is None:
            return ParamNotSet

        if isinstance(ordering, str):
            ordering_columns = ordering.split(",")
        else:
            ordering_columns = ordering

        print(ordering_columns)
        check_columns = allowed_columns is not None
        if check_columns and not allowed_columns:
            raise ValueError("allowed_columns must not be an empty set")

        result = []
        for column in ordering_columns:
            is_desc = column.startswith("-")
            clean_column = column[1:] if is_desc else column

            if check_columns and clean_column not in allowed_columns:
                raise fastapi.HTTPException(
                    status_code=400,
                    detail=f"Invalid column name: {clean_column}. Allowed columns: {', '.join(allowed_columns)}",
                )

            # Use SQLAlchemy's column reference instead of raw string
            # to prevent SQL injection attacks
            col = sa.column(clean_column)
            result.append(sa.desc(col) if is_desc else sa.asc(col))

        return result

    return _query_parser


__all__ = [
    "Limit",
    "Offset",
]
