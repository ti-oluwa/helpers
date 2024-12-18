from django.http import HttpResponse, JsonResponse
from typing import TypeVar

from .shortcuts import * # noqa

_HTTPResponse = TypeVar("_HTTPResponse", bound=HttpResponse)
_JSONResponse = TypeVar("_JSONResponse", bound=JsonResponse)
