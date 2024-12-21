import fastapi
import pydantic
import starlette.exceptions

from . import shortcuts


def generic_exception_handler(
    request: fastapi.Request, exc: Exception
) -> fastapi.Response:
    """Prepares and returns a properly formatted response for any exception."""
    return shortcuts.error(
        status_code=500,
        detail=str(exc),
    )


def validation_exception_handler(
    request: fastapi.Request, exc: fastapi.exceptions.ValidationException
) -> fastapi.Response:
    """Prepares and returns a properly formatted response for a validation exception."""
    return shortcuts.validation_error(errors=exc.errors())


def http_exception_handler(
    request: fastapi.Request, exc: starlette.exceptions.HTTPException
) -> fastapi.Response:
    """Prepares and returns a properly formatted response for an HTTP exception."""
    return shortcuts.error(
        status_code=exc.status_code,
        detail=exc.detail,
        headers=exc.headers,
    )


def pydantic_validation_error_handler(
    request: fastapi.Request, exc: pydantic.ValidationError
) -> fastapi.Response:
    """Prepares and returns a properly formatted response for a Pydantic validation exception."""
    return shortcuts.unprocessable_entity(errors=exc.errors())


def request_validation_error_handler(
    request: fastapi.Request, exc: fastapi.exceptions.RequestValidationError
) -> fastapi.Response:
    """Prepares and returns a properly formatted response for a request validation exception."""
    return shortcuts.unprocessable_entity(
        errors=exc.errors(), detail=str(exc.body) if exc.body else None
    )
