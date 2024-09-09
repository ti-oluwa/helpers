from ..exceptions import RequestError


class DataError(Exception):
    """Base class for data errors."""

    pass


class DataFetchError(RequestError, DataError):
    """Raised when there is an error fetching data from the Prembly API."""
