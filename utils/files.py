import functools
import mimetypes
import imghdr
import os
from io import BytesIO
from typing import Any, Callable, Dict, Optional, TypeVar, Union, Tuple, Coroutine
from django.core.files import File as DjangoFile
from django.core.files.uploadedfile import InMemoryUploadedFile
import httpx
import asyncio
from asgiref.sync import sync_to_async

from ..caching import ttl_cache, async_ttl_cache


T = TypeVar("T")
DownloadHandler = Callable[[httpx.Response], T]
AsyncDownloadHandler = Callable[[httpx.Response], Coroutine[Any, Any, T]]
_File = Union[str, bytes, BytesIO, DjangoFile]


def download(
    url: str,
    handler: Optional[DownloadHandler] = None,
    timeout: Optional[float] = None,
    request_kwargs: Optional[Dict[str, Any]] = None,
    cache_for: float = 300.0,
) -> T:
    """
    Download content from a URL and process it using a handler function.

    Uses the httpx library to make the request.

    :param url: The URL to download the file from.
    :param handler: The handler function to process the download response.
    If not provided, the raw content is returned.
    :param timeout: The timeout for the request.
    :param request_kwargs: Additional keyword arguments to pass to the request.
    :return: The result of the handler function if provided, otherwise the raw content.
    """
    if cache_for:
        return ttl_cache(download, ttl=cache_for)(
            url, handler, timeout, request_kwargs, 0
        )

    request_kwargs = request_kwargs or {}
    request_kwargs.pop("timeout", None)
    httpx_timeout = httpx.Timeout(timeout, connect=timeout)
    with httpx.Client(timeout=httpx_timeout, **request_kwargs) as client:
        response = client.get(url)
        response.raise_for_status()
        if not handler:
            return response.content
        return handler(response)


async def async_download(
    url: str,
    handler: Optional[AsyncDownloadHandler] = None,
    timeout: Optional[float] = None,
    request_kwargs: Optional[Dict[str, Any]] = None,
    cache_for: float = 300.0,
) -> T:
    """
    Download content from a URL asynchronously and process it using a handler function.

    Uses the httpx library to make the request.

    :param url: The URL to download the file from.
    :param handler: Async handler function to process the download response.
    If not provided, the raw content is returned.
    :param timeout: The timeout for the request.
    :param request_kwargs: Additional keyword arguments to pass to the request.
    :return: The result of the handler function if provided, otherwise the raw content.
    """
    if cache_for:
        return await async_ttl_cache(async_download, ttl=cache_for)(
            url, handler, timeout, request_kwargs, 0
        )

    request_kwargs = request_kwargs or {}
    request_kwargs.pop("timeout", None)
    httpx_timeout = httpx.Timeout(timeout, connect=timeout)
    async with httpx.AsyncClient(timeout=httpx_timeout, **request_kwargs) as client:
        response = await client.get(url)
        response.raise_for_status()
        if not handler:
            return response.content
        return await handler(response)


def multi_download(
    urls: Dict[str, Union[str, Tuple[str, DownloadHandler]]],
    default_handler: Optional[DownloadHandler] = None,
    timeout: int = None,
    request_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, T]:
    """
    Download content from multiple URLs and process them using a handler function.

    Uses the httpx library to make the requests.

    :param urls: A dictionary of URLs to download the files from.
    The keys are the names of the files and the values are the URLs
    or a tuple of URL and handler function.
    :param default_handler: The default handler function to process the download response.
    :param timeout: The timeout for the requests.
    :param request_kwargs: Additional keyword arguments to pass to the requests.
    :return: A mapping of the names of the files to the results of the handler functions, or raw content.
    """
    results = {}
    for name, url in urls.items():
        handler = default_handler
        if isinstance(url, tuple):
            url, handler = url
        results[name] = download(url, handler, timeout, request_kwargs)
    return results


def fast_multi_download(
    urls: Dict[str, Union[str, Tuple[str, DownloadHandler]]],
    default_handler: Optional[DownloadHandler] = None,
    timeout: Optional[float] = None,
    request_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, T]:
    """
    Download content from multiple URLs concurrently
    and process them using a handler function.

    Uses the httpx library to make the requests.

    :param urls: A dictionary of URLs to download the files from.
    The keys are the names of the files and the values are the URLs
    or a tuple of URL and handler function.
    :param default_handler: The default handler function to process the download response.
    :param timeout: The timeout for the requests.
    :param request_kwargs: Additional keyword arguments to pass to the requests.
    :return: A mapping of the names of the files to the results of the handler functions, or raw content.
    """
    if default_handler and not asyncio.iscoroutinefunction(default_handler):
        default_handler = sync_to_async(default_handler)

    async def download_and_handle(url, handler):
        if handler and not asyncio.iscoroutinefunction(handler):
            handler = sync_to_async(handler)
        return await async_download(url, handler, timeout, request_kwargs)

    async def download_all():
        tasks = []
        for _, url in urls.items():
            handler = default_handler
            if isinstance(url, tuple):
                url, handler = url

            tasks.append(download_and_handle(url, handler))
        return await asyncio.gather(*tasks)

    results = asyncio.run(download_all())
    return dict(zip(urls.keys(), results))


def response_to_in_memory_file(response: httpx.Response) -> InMemoryUploadedFile:
    """Download response handler. Returns response content as an `InMemoryUploadedFile`"""
    url = response.url
    content_type = response.headers.get("Content-Type", "application/octet-stream")
    charset = response.charset_encoding
    file_io = BytesIO(response.content)
    file_name = url.path.split("/")[-1]
    return InMemoryUploadedFile(
        file_io,
        field_name=None,
        name=file_name,
        content_type=content_type,
        size=file_io.getbuffer().nbytes,
        charset=charset,
    )


async_response_to_in_memory_file = sync_to_async(response_to_in_memory_file)

download_as_in_memory_file = functools.partial(
    download, handler=response_to_in_memory_file
)
"""`download` function with response returned as an `InMemoryUploadedFile`"""

async_download_as_in_memory_file = functools.partial(
    async_download, handler=async_response_to_in_memory_file
)
"""`async_download` function with response returned as an `InMemoryUploadedFile`"""


IMAGE_EXTENSIONS = ("jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "svg", "ico")
VIDEO_EXTENSIONS = ("mp4", "webm", "mkv", "flv", "avi", "mov", "wmv", "mpg", "mpeg")
AUDIO_EXTENSIONS = ("mp3", "wav", "ogg", "flac", "aac", "wma", "m4a", "opus")

def infer_file_type(file: Union[str, DjangoFile]) -> str:
    """
    Infers the type of a file (video, image, audio, ...) based on its content or extension.

    :param file: The path to the file whose type needs to be determined.

    :return: The inferred file type, which can be "video", "image", "audio", "<ext>" or "unknown" 
         if the file type cannot be determined.
    """
    # Check if it's an image by inspecting the file header
    if imghdr.what(file):
        return "image"
    
    # Infer file type using the MIME type based on file extension
    if isinstance(file, DjangoFile):
        file = file.name
    
    mime_type, _ = mimetypes.guess_type(file)
    if mime_type:
        if mime_type.startswith("video"):
            return "video"
        elif mime_type.startswith("audio"):
            return "audio"
    
    return infer_file_type_from_extension(file)


def infer_file_type_from_extension(file: str):
    """
    Infers the type of a file (video, image, audio, ...) based on its extension.

    :param file: The path to the file whose type needs to be determined.

    :return: The inferred file type, which can be "video", "image", "audio", "<ext>" or "unknown" 
         if the file type cannot be determined.
    """
    _, ext = os.path.splitext(file)
    if ext:
        ext = ext[1:].lower()
        if ext in IMAGE_EXTENSIONS:
            return "image"
        if ext in VIDEO_EXTENSIONS:
            return "video"
        if ext in AUDIO_EXTENSIONS:
            return "audio"
        return ext
    
    return "unknown"
