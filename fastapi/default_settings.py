import fastapi
import pydantic
import starlette.exceptions


INSTALLED_APPS = []

APP = {
    "debug": True,
}

DEFAULT_DEPENDENCIES = []

TIMEZONE = "UTC"

AUTH_USER_MODEL = None

MIDDLEWARE = [
    "helpers.fastapi.requests.middlewares.MaintenanceMiddleware",
    "helpers.fastapi.middlewares.core.AllowedHostsMiddleware",
    "helpers.fastapi.middlewares.core.AllowedIPsMiddleware",
    "helpers.fastapi.middlewares.core.HostBlacklistMiddleware",
    "helpers.fastapi.middlewares.core.IPBlacklistMiddleware",
    "helpers.fastapi.middlewares.users.ConnectedUserMiddleware",
    "helpers.fastapi.response.middlewares.FormatJSONResponseMiddleware",
]

ALLOWED_HOSTS = ["*"]

PASSWORD_SCHEMES = ["md5_crypt"]

PASSWORD_VALIDATORS = [
    "helpers.fastapi.password_validation.common_password_validator",
    "helpers.fastapi.password_validation.mixed_case_validator",
    "helpers.fastapi.password_validation.special_characters_validator",
    "helpers.fastapi.password_validation.digit_validator",
]

ALLOWED_IPS = ["*"]

BLACKLISTED_HOSTS = []

BLACKLISTED_IPS = []

MAILING = {}

RESPONSE_FORMATTER = {
    "formatter": "default",
    "exclude": [r"/redoc*", r"/docs*", r"/openapi\.json"],
    "enforce_format": True,
}

MAINTENANCE_MODE = {"status": "off", "message": "default:minimal_dark"}


EXCEPTION_HANDLERS = {
    fastapi.exceptions.ValidationException: "helpers.fastapi.response.exception_handling.validation_exception_handler",
    starlette.exceptions.HTTPException: "helpers.fastapi.response.exception_handling.http_exception_handler",
    Exception: "helpers.fastapi.response.exception_handling.generic_exception_handler",
    pydantic.ValidationError: "helpers.fastapi.response.exception_handling.pydantic_validation_error_handler",
    fastapi.exceptions.RequestValidationError: "helpers.fastapi.response.exception_handling.request_validation_error_handler",
}
