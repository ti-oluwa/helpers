from enum import StrEnum
from typing import Any, List, Dict, Optional, Union

from starlette.responses import JSONResponse
from pydantic import BaseModel, Field


class Status(StrEnum):
    """Response status."""

    SUCCESS = "success"
    ERROR = "error"


class Schema(BaseModel):
    """Response schema."""

    status: Status = Field(
        ..., description="The status of the response, e.g., 'success' or 'error'."
    )
    message: str = Field(..., description="A short message describing the response.")
    detail: Optional[str] = Field(
        None, description="Optional detailed information about the response."
    )
    data: Optional[Any] = Field(
        None, description="Optional data payload for the response."
    )
    errors: Optional[Union[List[Any], Dict[str, Any]]] = Field(
        None, description="Optional error details, if applicable."
    )


def json_response(
    message: str = "Request successful!",
    *,
    status: Status = Status.SUCCESS,
    detail: Optional[str] = None,
    data: Optional[Any] = None,
    errors: Optional[Union[List[Any], Dict[str, Any]]] = None,
    status_code: int = 200,
    **kwargs,
) -> JSONResponse:
    """Returns a JSON response with a structured payload."""
    schema = Schema(
        status=status,
        message=message,
        detail=detail,
        data=data,
        errors=errors,
    )
    return JSONResponse(
        content=schema.model_dump(mode="json"),
        status_code=status_code,
        **kwargs,
    )


def success(
    message: str = "Request successful!",
    data: Optional[Any] = None,
    status_code: int = 200,
    **kwargs,
) -> JSONResponse:
    """Use for successful requests."""
    return json_response(
        message=message,
        status=Status.SUCCESS,
        data=data,
        status_code=status_code,
        **kwargs,
    )


def error(
    message: str = "Oops! An error occurred",
    errors: Optional[Union[List[Any], Dict[str, Any]]] = None,
    detail: Optional[str] = None,
    status_code: int = 500,
    **kwargs,
) -> JSONResponse:
    """Use for error responses."""
    return json_response(
        message=message,
        status=Status.ERROR,
        errors=errors,
        detail=detail,
        status_code=status_code,
        **kwargs,
    )


def not_modified(message: str = "Not modified", **kwargs) -> JSONResponse:
    """Use when a request is not modified."""
    return success(message, status_code=304, **kwargs)


def created(
    message: str = "Resource created", data: Union[Dict, List] = None, **kwargs
) -> JSONResponse:
    """Use when a resource is created."""
    return success(message, data=data, status_code=201, **kwargs)


def accepted(
    message: str = "Request accepted", data: Union[Dict, List] = None, **kwargs
) -> JSONResponse:
    """Use when a request is accepted."""
    return success(message, data=data, status_code=202, **kwargs)


def no_content(
    message: str = "No content", data: Union[Dict, List] = None, **kwargs
) -> JSONResponse:
    """Use when there is no content to return."""
    return success(message, data=data, status_code=204, **kwargs)


def partial_content(
    message: str = "Partial content", data: Union[Dict, List] = None, **kwargs
) -> JSONResponse:
    """Use when there is partial content to return."""
    return success(message, data=data, status_code=206, **kwargs)


def already_exists(message: str = "Resource already exists", **kwargs) -> JSONResponse:
    """Use when a resource already exists."""
    return error(message, status_code=409, **kwargs)


def validation_error(errors: Union[Dict, List] = None, **kwargs) -> JSONResponse:
    """Use when a validation error occurs."""
    message = "Validation failed"
    return error(message, errors=errors, status_code=422, **kwargs)


def forbidden(
    message: str = "You don't have permission to access this resource", **kwargs
) -> JSONResponse:
    """Use when a user is forbidden from accessing a resource."""
    return error(message, errors=None, status_code=403, **kwargs)


def unprocessable_entity(
    message: str = "Unprocessable request", **kwargs
) -> JSONResponse:
    """Use when a request is unprocessable."""
    return error(message, status_code=422, **kwargs)


def bad_request(
    message: str = "Bad Request", status_code: int = 400, **kwargs
) -> JSONResponse:
    """Use when a request is bad."""
    return error(message, status_code=status_code, **kwargs)


def notfound(message: str = "Resource not found!", **kwargs) -> JSONResponse:
    """Use when a resource is not found."""
    return error(message, errors=None, status_code=404, **kwargs)


def unauthorized(
    message: str = "You don't have authorization to access this resource", **kwargs
) -> JSONResponse:
    """Use when a user is unauthorized to access a resource."""
    return error(message, errors=None, status_code=401, **kwargs)


def server_error(
    message: str = "Internal Server Error", status_code: int = 500, **kwargs
) -> JSONResponse:
    """Use when a server error occurs."""
    return error(message, errors=None, status_code=status_code, **kwargs)


def conflict(
    message: str = "Data conflict!", status_code: int = 409, **kwargs
) -> JSONResponse:
    """Use when a data conflict occurs."""
    return error(message, status_code=status_code, **kwargs)


def failed_dependency(message: str = "Failed dependency", **kwargs) -> JSONResponse:
    """Use when a request fails due to a dependency."""
    return error(message, status_code=424, **kwargs)


def method_not_allowed(
    message: str = "Method not allowed", status_code: int = 405, **kwargs
) -> JSONResponse:
    """Use when a method is not allowed."""
    return error(message, errors=None, status_code=status_code, **kwargs)


def not_implemented(
    message: str = "Not implemented", status_code: int = 501, **kwargs
) -> JSONResponse:
    """Use when a method is not implemented."""
    return error(message, errors=None, status_code=status_code, **kwargs)


def expectation_failed(message: str = "Expectation failed", **kwargs) -> JSONResponse:
    """Use when the server cannot meet the expectation of the client."""
    return error(message, status_code=417, **kwargs)


def not_acceptable(message: str = "Not acceptable", **kwargs) -> JSONResponse:
    """Use when the server cannot provide the requested content type."""
    return error(message, status_code=406, **kwargs)


def payment_required(message: str = "Payment required", **kwargs) -> JSONResponse:
    """Use when payment is required to access a resource."""
    return error(message, status_code=402, **kwargs)


def too_many_requests(message: str = "Too many requests", **kwargs) -> JSONResponse:
    """Use when the client has sent too many requests in a given amount of time."""
    return error(message, errors=None, status_code=429, **kwargs)


def gone(message: str = "Resource gone", **kwargs) -> JSONResponse:
    """Use when a resource is no longer available."""
    return error(message, errors=None, status_code=410, **kwargs)


def too_large(message: str = "Request too large", **kwargs) -> JSONResponse:
    """Use when a request is too large."""
    return error(message, status_code=413, **kwargs)


def unsupported_media_type(
    message: str = "Unsupported media type", **kwargs
) -> JSONResponse:
    """Use when the server cannot process the media type of the request."""
    return error(message, status_code=415, **kwargs)


def precondition_failed(message: str = "Precondition failed", **kwargs) -> JSONResponse:
    """Use when a precondition in the request headers is not met."""
    return error(message, status_code=412, **kwargs)


def too_early(message: str = "Too early", **kwargs) -> JSONResponse:
    """Use when the client sends a request too early."""
    return error(message, status_code=425, **kwargs)


def service_unavailable(message: str = "Service unavailable", **kwargs) -> JSONResponse:
    """Use when the server is temporarily unavailable."""
    return error(message, errors=None, status_code=503, **kwargs)


def under_maintenance(
    message: str = "Service under maintenance", **kwargs
) -> JSONResponse:
    """Use when the server is under maintenance."""
    return service_unavailable(message, **kwargs)


def unavailable_for_legal_reasons(
    message: str = "Unavailable for legal reasons", **kwargs
) -> JSONResponse:
    """Use when a resource is unavailable for legal reasons."""
    return error(message, errors=None, status_code=451, **kwargs)


__all__ = [
    "json_response",
    "success",
    "error",
    "not_modified",
    "created",
    "accepted",
    "no_content",
    "partial_content",
    "already_exists",
    "validation_error",
    "forbidden",
    "unprocessable_entity",
    "bad_request",
    "notfound",
    "unauthorized",
    "server_error",
    "conflict",
    "failed_dependency",
    "method_not_allowed",
    "not_implemented",
    "expectation_failed",
    "not_acceptable",
    "payment_required",
    "too_many_requests",
    "gone",
    "too_large",
    "unsupported_media_type",
    "precondition_failed",
    "too_early",
    "service_unavailable",
    "under_maintenance",
    "unavailable_for_legal_reasons",
]
