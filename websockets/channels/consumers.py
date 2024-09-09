import typing
from contextlib import asynccontextmanager
from channels.generic.websocket import AsyncConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import functools

from .events import IncomingEvent, OutgoingEvent, EventStatus, EventType, BaseEventType
from helpers.logging import log_exception
from helpers.utils.misc import merge_enums
from helpers.utils.choice import ExtendedEnum


@asynccontextmanager
async def capture_exception(
    consumer: AsyncConsumer, exc_class: typing.Type[Exception] = None
):
    """Capture exceptions and send an outgoing error event back to the client."""
    exc_class = exc_class or Exception
    try:
        yield
    except exc_class as exc:
        log_exception(exc)
        message = exc.args[0] if exc.args else str(exc)
        if not isinstance(message, str):
            message = "An error occurred"

        errors = getattr(exc, "detail", None) or getattr(exc, "message_dict", None)
        outgoing_event = OutgoingEvent(
            type=EventType.ErrorOccurred,
            status=EventStatus.ERROR,
            message=message,
            errors=errors,
        )
        await consumer.send(outgoing_event.as_json())
    finally:
        pass


class AsyncJsonWebsocketEventConsumer(AsyncJsonWebsocketConsumer):
    """
    Custom async JSON websocket consumer with mechanisms
    for handling events.

    Check `helpers/websockets/channels/events.py` for more details
    on events
    """

    event_type: typing.Type[BaseEventType] = EventType
    """Enum containing expected/acceptable event types"""

    async def on_connect(self):
        """Called after a connection is established/accepted."""
        pass

    async def on_disconnect(self, close_code):
        """Called after a connection is closed."""
        pass

    async def on_receive(self, content, **kwargs):
        """Called immediately after a message is received before it is processed."""
        pass

    async def connect(self):
        await super().connect()
        await self.on_connect()

    async def disconnect(self, close_code):
        await self.on_disconnect(close_code)

    @classmethod
    @functools.cache
    def get_event_type(cls) -> ExtendedEnum:
        # Merge the specific event type class and the default one
        # so default events can also be accepted
        return merge_enums(cls.event_type.__name__, *set((cls.event_type, EventType)))

    async def receive_json(self, content, **kwargs):
        await self.on_receive(content, **kwargs)

        async with capture_exception(self):
            incoming_event = IncomingEvent.load(content, type(self).get_event_type())
            return await self.handle_incoming_event(incoming_event)

    async def error_occurred(self, event):
        return await self.send_json(event)

    async def handle_incoming_event(self, incoming_event: IncomingEvent):
        """Calls the appropriate handler for the incoming event type."""
        handler = getattr(self, f"handle_{incoming_event.type.value}", None)
        if handler:
            return await handler(incoming_event)
        # Ignore incoming events with no defined handler
        return None

    # INCOMING EVENT HANDLERS GO HERE

    async def handle_ping(self, incoming_event: IncomingEvent):
        outgoing_event = OutgoingEvent(
            type=EventType.Pong,
            message="Pong!",
            data=incoming_event.data,
        )
        await self.send_json(outgoing_event.as_dict())
