from helpers.dependencies import required_deps

required_deps({"django": "https://www.djangoproject.com/"})


from django.http import HttpResponse, JsonResponse
from typing import TypeVar

from .shortcuts import * # noqa

HTTPResponse = TypeVar("HTTPResponse", bound=HttpResponse)
JSONResponse = TypeVar("JSONResponse", bound=JsonResponse)
