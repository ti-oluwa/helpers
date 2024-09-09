from django.http import HttpResponse, JsonResponse
from typing import TypeVar

from .shortcuts import *


HTTPResponse = TypeVar("HTTPResponse", bound=HttpResponse)
JSONResponse = TypeVar("JSONResponse", bound=JsonResponse)
