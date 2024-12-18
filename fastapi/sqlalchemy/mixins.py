import uuid
import sqlalchemy as sa
from sqlalchemy.orm import declarative_mixin

from helpers.fastapi.utils import timezone


@declarative_mixin
class TimestampMixin:
    """Adds timestamp fields to the database model"""

    created_at = sa.Column(
        sa.DateTime(timezone=True),
        default=timezone.now,
        nullable=False,
        doc="The timestamp of creation",
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        default=timezone.now,
        onupdate=timezone.now,
        nullable=False,
        doc="The timestamp of the last update",
    )


@declarative_mixin
class UUIDPrimaryKeyMixin:
    """Adds a UUID Field, `id`, as the primary key of the database model"""

    id = sa.Column(
        sa.UUID,
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        doc="The primary key of the model",
    )

