from helpers.dependencies import deps_required

deps_required({"django": "https://www.djangoproject.com/"})


from django.http import HttpResponse, JsonResponse
from typing import TypeVar

from .shortcuts import * # noqa

HTTPResponse = TypeVar("HTTPResponse", bound=HttpResponse)
JSONResponse = TypeVar("JSONResponse", bound=JsonResponse)
