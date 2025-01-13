from helpers.generics.data_utils.exceptions import DataError


class FieldError(DataError, ValueError):
    """Exception raised for field-related errors."""

    pass
