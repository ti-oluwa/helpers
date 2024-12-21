import typing

from starlette.requests import Request

_T = typing.TypeVar("_T")
_Request = typing.TypeVar("_Request", bound=Request)


class _PaginatedData(typing.Generic[_T], typing.TypedDict):
    count: int
    limit: int
    offset: int
    next: typing.Optional[str]
    previous: typing.Optional[str]
    data: typing.Iterable[_T]


def paginated_data(
    request: _Request,
    data: typing.Iterable[_T],
    limit: int,
    offset: int,
    total: typing.Optional[int] = None,
    query_params: typing.Optional[typing.Dict[str, typing.Any]] = None,
) -> _PaginatedData[_T]:
    """
    Convert iterable data resulting from pagination
    to structured data with necessary pagination info.

    :param request: FastAPI request of the route/endpoint.
    :param data: An iterable of data items resulting from pagination.
    :param limit: The limit value used for pagination.
    :param offset: The offset value used for pagination.
    :param total: The total number of items available for pagination.
    :param query_params: Additional query parameters to include in the pagination links.
        This overrides any existing query parameters in the request URL, excluding `offset`.
    :return: A dictionary representing the structured paginated data.
    """
    next_offset = offset + limit
    prev_offset = offset - limit
    next_url = None
    prev_url = None
    count = len(data)

    request_query_params = dict(request.query_params)
    if query_params:
        request_query_params.update(query_params)

    request_query_params.pop("offset", None)
    if total:
        # If we have the total number of items, we can determine if there are more
        # items to fetch by checking if the next offset is less than the total.
        # If it is, then there are more items to fetch.
        if next_offset < total:
            next_url = request.url.replace_query_params(
                **request_query_params, offset=next_offset
            )
    else:
        # If we get exactly the number of items we requested, there might be more
        # items to fetch. So we can add a next link.
        if count == limit:
            next_url = request.url.replace_query_params(
                **request_query_params, offset=next_offset
            )
        # Else, if we get less than the number of items we requested, then it
        # mostlikely means that we have reached the end of the list.

    if prev_offset >= 0:
        prev_url = request.url.replace_query_params(
            **request_query_params, offset=prev_offset
        )

    return _PaginatedData(
        count=len(data),
        limit=limit,
        offset=offset,
        next=str(next_url) if next_url else None,
        previous=str(prev_url) if prev_url else None,
        data=data,
    )


__all__ = [
    "paginated_data",
]
