
from starlette.responses import Response, JSONResponse
from typing import TypeVar

from .shortcuts import * # noqa

_Response = TypeVar("_Response", bound=Response)
_JSONResponse = TypeVar("_JSONResponse", bound=JSONResponse)
