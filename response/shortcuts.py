"""Response Shortcuts"""

from django.http import JsonResponse
from typing import Dict, List, Union


def success(
    message: str = "Request successful!",
    data: Union[Dict, List] = None,
    status_code: int = 200,
    **kwargs,
) -> JsonResponse:
    """Use when a request is successful."""
    response_data = {
        "status": "success",
        "message": message,
        "data": data,
    }
    return JsonResponse(response_data, status=status_code, **kwargs)


def error(
    message: str = "Oops! An error occurred",
    errors: Union[Dict, List] = None,
    status_code: int = 500,
    **kwargs,
) -> JsonResponse:
    """Use when an error occurs."""
    response_data = {
        "status": "error",
        "message": message,
        "errors": errors,
    }
    return JsonResponse(response_data, status=status_code, **kwargs)


def custom(
    message: str = "Request successful!",
    data: Union[Dict, List] = None,
    status_code: int = 200,
    status: str = "success",
    **kwargs,
) -> JsonResponse:
    """Use to create a custom response."""
    response_data = {
        "status": status,
        "message": message,
        "data": data,
    }
    return JsonResponse(response_data, status=status_code, **kwargs)


def not_modified(message: str = "Not modified", **kwargs) -> JsonResponse:
    """Use when a request is not modified."""
    return success(message, status_code=304, **kwargs)


def created(
    message: str = "Resource created", data: Union[Dict, List] = None, **kwargs
) -> JsonResponse:
    """Use when a resource is created."""
    return success(message, data, 201, **kwargs)


def accepted(
    message: str = "Request accepted", data: Union[Dict, List] = None, **kwargs
) -> JsonResponse:
    """Use when a request is accepted."""
    return success(message, data, 202, **kwargs)


def no_content(
    message: str = "No content", data: Union[Dict, List] = None, **kwargs
) -> JsonResponse:
    """Use when there is no content to return."""
    return success(message, data, 204, **kwargs)


def partial_content(
    message: str = "Partial content", data: Union[Dict, List] = None, **kwargs
) -> JsonResponse:
    """Use when there is partial content to return."""
    return success(message, data, 206, **kwargs)


def already_exists(message: str = "Resource already exists", **kwargs) -> JsonResponse:
    """Use when a resource already exists."""
    return error(message, None, 409, **kwargs)


def validation_error(errors: Union[Dict, List] = None, **kwargs) -> JsonResponse:
    """Use when a validation error occurs."""
    message = "Validation failed"
    return error(message, errors, 400, **kwargs)


def forbidden(
    message: str = "You don't have permission to access this resource", **kwargs
) -> JsonResponse:
    """Use when a user is forbidden from accessing a resource."""
    return error(message, None, 403, **kwargs)


def unprocessable_entity(
    message: str = "Unprocessable request", **kwargs
) -> JsonResponse:
    """Use when a request is unprocessable."""
    return error(message, None, 422, **kwargs)


def bad_request(
    message: str = "Bad Request", status_code: int = 400, **kwargs
) -> JsonResponse:
    """Use when a request is bad."""
    return error(message, None, status_code, **kwargs)


def notfound(message: str = "Resource not found!", **kwargs) -> JsonResponse:
    """Use when a resource is not found."""
    return error(message, None, 404, **kwargs)


def unauthorized(
    message: str = "You don't have authorization to access this resource", **kwargs
) -> JsonResponse:
    """Use when a user is unauthorized to access a resource."""
    return error(message, None, 401, **kwargs)


def server_error(
    message: str = "Internal Server Error", status_code: int = 500, **kwargs
) -> JsonResponse:
    """Use when a server error occurs."""
    return error(message, None, status_code, **kwargs)


def conflict(
    message: str = "Data conflict!", status_code: int = 409, **kwargs
) -> JsonResponse:
    """Use when a data conflict occurs."""
    return error(message, None, status_code, **kwargs)


def failed_dependency(message: str = "Failed dependency", **kwargs) -> JsonResponse:
    """Use when a request fails due to a dependency."""
    return error(message, None, 424, **kwargs)


def method_not_allowed(
    message: str = "Method not allowed", status_code: int = 405, **kwargs
) -> JsonResponse:
    """Use when a method is not allowed."""
    return error(message, None, status_code, **kwargs)


def not_implemented(
    message: str = "Not implemented", status_code: int = 501, **kwargs
) -> JsonResponse:
    """Use when a method is not implemented."""
    return error(message, None, status_code, **kwargs)


def expectation_failed(message: str = "Expectation failed", **kwargs) -> JsonResponse:
    """Use when the server cannot meet the expectation of the client."""
    return error(message, None, 417, **kwargs)


def not_acceptable(message: str = "Not acceptable", **kwargs) -> JsonResponse:
    """Use when the server cannot provide the requested content type."""
    return error(message, None, 406, **kwargs)


def payment_required(message: str = "Payment required", **kwargs) -> JsonResponse:
    """Use when payment is required to access a resource."""
    return error(message, None, 402, **kwargs)


def too_many_requests(message: str = "Too many requests", **kwargs) -> JsonResponse:
    """Use when the client has sent too many requests in a given amount of time."""
    return error(message, None, 429, **kwargs)


def gone(message: str = "Resource gone", **kwargs) -> JsonResponse:
    """Use when a resource is no longer available."""
    return error(message, None, 410, **kwargs)


def too_large(message: str = "Request too large", **kwargs) -> JsonResponse:
    """Use when a request is too large."""
    return error(message, None, 413, **kwargs)


def unsupported_media_type(
    message: str = "Unsupported media type", **kwargs
) -> JsonResponse:
    """Use when the server cannot process the media type of the request."""
    return error(message, None, 415, **kwargs)


def precondition_failed(message: str = "Precondition failed", **kwargs) -> JsonResponse:
    """Use when a precondition in the request headers is not met."""
    return error(message, None, 412, **kwargs)


def too_early(message: str = "Too early", **kwargs) -> JsonResponse:
    """Use when the client sends a request too early."""
    return error(message, None, 425, **kwargs)


def service_unavailable(message: str = "Service unavailable", **kwargs) -> JsonResponse:
    """Use when the server is temporarily unavailable."""
    return error(message, None, 503, **kwargs)


def under_maintenance(
    message: str = "Service under maintenance", **kwargs
) -> JsonResponse:
    """Use when the server is under maintenance."""
    return service_unavailable(message, **kwargs)


def unavailable_for_legal_reasons(
    message: str = "Unavailable for legal reasons", **kwargs
) -> JsonResponse:
    """Use when a resource is unavailable for legal reasons."""
    return error(message, None, 451, **kwargs)


__all__ = [
    "success",
    "error",
    "custom",
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
