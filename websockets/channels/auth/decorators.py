import typing
import functools
import asyncio
import inspect
from channels.generic.websocket import AsyncConsumer
from django.core.exceptions import ImproperlyConfigured


AUTH_REQUIRED_CODE = 4003  # Permission denied error code
AUTH_REQUIRED_MSG = "Authentication required!"

Consumer = typing.TypeVar("Consumer", bound=AsyncConsumer)


def authentication_required(
    consumer_cls: typing.Optional[typing.Type[Consumer]] = None,
    *,
    code: int = AUTH_REQUIRED_CODE,
    message: str = AUTH_REQUIRED_MSG,
) -> typing.Union[typing.Callable[[Consumer], Consumer], typing.Type[Consumer]]:
    """
    Websocket consumer decorator.

    Checks that the consumer user is authenticated before allowing access

    :param consumer_cls: The consumer class to decorate
    :param code: The close code to send if the user is not authenticated
    :param message: The close message to send if the user is not authenticated
    """
    if consumer_cls is None:
        # If the decorator is called with arguments
        # return a partial function with the arguments
        # that will be used to decorate the consumer
        consumer_decorator = functools.partial(
            authentication_required, code=code, message=message
        )
        return consumer_decorator

    if not (inspect.isclass(consumer_cls) and issubclass(consumer_cls, AsyncConsumer)):
        raise ImproperlyConfigured(
            "Decorated object must be a websocket consumer class"
        )

    def method_decorator(method):
        if asyncio.iscoroutinefunction(method):

            async def wrapper(*args, **kwargs):
                # Get the websocket object from the first argument
                consumer: Consumer = args[0]
                user = consumer.scope.get("user")
                # Check if the user is authenticated
                if not user or not user.is_authenticated:
                    return await consumer.close(code=code, reason=message)

                return await method(*args, **kwargs)
        else:

            def wrapper(*args, **kwargs):
                # Get the websocket object from the first argument
                consumer: Consumer = args[0]
                user = consumer.scope.get("user")
                # Check if the user is authenticated
                if not user or not user.is_authenticated:
                    return consumer.close(code=code, reason=message)

                return method(*args, **kwargs)

        return functools.wraps(method)(wrapper)

    consumer_cls.connect = method_decorator(consumer_cls.connect)
    return consumer_cls
