import datetime
import uuid
import sqlalchemy as sa
from sqlalchemy import orm

from helpers.fastapi.utils import timezone


@orm.declarative_mixin
class TimestampMixin:
    """Adds timestamp fields to the database model"""

    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        sa.DateTime(timezone=True),
        default=timezone.now,
        nullable=False,
        doc="The timestamp of creation",
    )
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        sa.DateTime(timezone=True),
        default=timezone.now,
        onupdate=timezone.now,
        nullable=False,
        doc="The timestamp of the last update",
    )


@orm.declarative_mixin
class UUIDPrimaryKeyMixin:
    """Adds a UUID Field, `id`, as the primary key of the database model"""

    id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.UUID,
        primary_key=True,
        index=True,
        default=uuid.uuid4,
        doc="The primary key of the model",
    )

