from typing import Any, Union
import functools
import asyncio
from asgiref.sync import sync_to_async

from . import CBV, FBV, is_view_class


class ViewContextDecorator(object):
    """
    Mixin that adapts a context manager to be used as a decorator on Django views.

    Works with both sync and async views.
    """

    def __call__(self, decorated: Union[type[CBV], FBV]) -> type[CBV] | FBV:
        if is_view_class(decorated):
            return self._decorate_view_class(decorated)
        return self._decorate_view_function(decorated)

    def _decorate_view_class(self, cls: type[CBV]) -> type[CBV]:
        """Decorate class-based view."""
        if not hasattr(cls, "http_method_names"):
            return cls
        return self._decorate_handlers(cls)

    def _decorate_handlers(self, view: type[CBV]) -> type[CBV]:
        """Decorate all handler methods of a class-based view."""
        for method in view.http_method_names:
            method = method.lower()
            handler = getattr(view, method, None)
            if not handler:
                continue
            decorated_handler = self._decorate_view_function(handler)
            setattr(view, method, decorated_handler)
        return view

    def _decorate_view_function(self, view: FBV) -> FBV:
        """Decorate function-based view."""
        if asyncio.iscoroutinefunction(view):
            return self._handle_async_view_function(view)
        return self._handle_sync_view_function(view)

    def _handle_async_view_function(self, view: FBV) -> FBV:
        """Handle async function-based view."""

        @functools.wraps(view)
        async def wrapper(*args: Any, **kwargs: Any):
            async with self:
                return await view(*args, **kwargs)

        return wrapper

    def _handle_sync_view_function(self, view: FBV):
        """Handle sync function-based view."""

        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            with self:
                return view(*args, **kwargs)

        return wrapper

    def __enter__(self):
        return self

    def __exit__(
        self, exc_type: type[BaseException], exc_value: BaseException, traceback
    ) -> bool:
        return False

    async def __aenter__(self):
        return await sync_to_async(self.__enter__)()

    async def __aexit__(
        self, exc_type: type[BaseException], exc_value: BaseException, traceback
    ) -> bool:
        return await sync_to_async(self.__exit__)(exc_type, exc_value, traceback)
