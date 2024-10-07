import typing
import json
from dataclasses import dataclass, KW_ONLY
from django.utils.translation import gettext as _

from helpers.utils.choice import ExtendedEnum
from .exceptions import InvalidData


class BaseEventType(ExtendedEnum):
    """Types of events."""

    pass


class EventType(BaseEventType):
    """Default event types"""

    Ping = _("ping")
    Pong = _("pong")
    ErrorOccurred = _("error_occurred")


@dataclass(slots=True)
class Event:
    """Base class for events."""

    type: BaseEventType
    data: typing.Optional[typing.Any] = None

    def as_dict(self) -> typing.Dict[str, typing.Any]:
        """Return the event as a dictionary."""
        return {
            "type": self.type.value,
            "message": self.message,
        }

    def as_json(self) -> str:
        """Return the event as a JSON string."""
        return json.dumps(self.as_dict())

    @classmethod
    def load(
        cls,
        data: typing.Union[str, typing.Dict[str, typing.Any]],
        expected_type: typing.Type[BaseEventType],
    ):
        """Load an event from a JSON string or a dictionary."""
        if isinstance(data, str):
            return cls.from_json(data, expected_type)
        return cls.from_dict(data, expected_type)

    @classmethod
    def from_json(cls, json_str: str, expected_type: typing.Type[BaseEventType]):
        """Load an event from a JSON string."""
        data: typing.Dict = json.loads(json_str)
        return cls.from_dict(data, expected_type)

    @classmethod
    def from_dict(
        cls,
        data: typing.Dict[str, typing.Any],
        expected_type: typing.Type[BaseEventType],
    ):
        """Load an event from a dictionary."""
        type_str = data.pop("type", None)
        if not type_str:
            raise InvalidData(
                {
                    "type": [_("Missing 'type' key in event data.")],
                }
            )

        event_type = expected_type(type_str)
        return cls(type=event_type, **data)

    def ensure_data(self, *keys: str) -> bool:
        """
        Validate that the data contains the specified keys.

        :param keys: The keys that should be present in the event data.
        :return: True if the data contains all the required keys.
        :raises InvalidData: If any of the required keys are missing.
        """
        data = self.data or {}
        errors = []
        for key in keys:
            if key == "":
                continue

            if key not in data:
                errors.append(_(f"Missing key '{key}' in event data."))

        if errors:
            raise InvalidData(
                {
                    "data": errors,
                }
            )
        return True


@dataclass(slots=True)
class IncomingEvent(Event):
    """Event from clients received by websocket consumer."""


class EventStatus(ExtendedEnum):
    OK = "ok"
    ERROR = "error"


@dataclass(slots=True)
class OutgoingEvent(Event):
    """Event from websocket consumer to be sent to clients."""

    _: KW_ONLY
    status: EventStatus = EventStatus.OK
    message: str = "An event occurred."
    errors: typing.Optional[
        typing.Union[typing.Dict[str, typing.Any], typing.List[str], str]
    ] = None

    def as_dict(self) -> typing.Dict[str, typing.Any]:
        return {
            "status": self.status.value,
            **super(OutgoingEvent, self).as_dict(),
            "data": self.data,
            "errors": self.errors,
        }
