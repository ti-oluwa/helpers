import collections
import collections.abc
import datetime
from tkinter import N
import typing
from annotated_types import MaxLen
import sqlalchemy as sa
from sqlalchemy import orm
import sqlalchemy_utils as sa_utils

from helpers.fastapi.sqlalchemy import models
from helpers.fastapi.config import settings
from helpers.fastapi.apps import discover_apps, discover_models
from helpers.fastapi.utils import timezone
from helpers.fastapi.utils.password_validation import validate_password
from helpers.generics.utils.misc import is_iterable


class AbstractBaseUser(models.Model):
    __abstract__ = True

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return not self.is_authenticated


class AbstractUserMeta(models.ModelBaseMeta):
    def __new__(cls, *args, **kwargs):
        new_cls = super().__new__(cls, *args, **kwargs)
        cls.check_username_field(new_cls)
        cls.check_required_fields(new_cls)
        return new_cls

    @staticmethod
    def check_username_field(new_cls):
        field = new_cls.get_fields().get(new_cls.USERNAME_FIELD, None)
        if not field:
            raise ValueError(
                f"USERNAME_FIELD '{new_cls.USERNAME_FIELD}' not found in model {new_cls.__name__}"
            )
        if field.column.nullable:
            raise ValueError(
                f"USERNAME_FIELD '{new_cls.USERNAME_FIELD}' must not be nullable"
            )
        if not field.column.unique:
            raise ValueError(
                f"USERNAME_FIELD '{new_cls.USERNAME_FIELD}' must be unique"
            )
        return None

    @staticmethod
    def check_required_fields(new_cls):
        for field in new_cls.REQUIRED_FIELDS:
            if field not in new_cls.get_fields():
                raise ValueError(
                    f"REQUIRED_FIELDS '{field}' not found in model {new_cls.__name__}"
                )

        if isinstance(new_cls.REQUIRED_FIELDS, collections.abc.Mapping):
            for field_name, value in new_cls.REQUIRED_FIELDS.items():
                if not is_iterable(value):
                    raise ValueError(
                        f"REQUIRED_FIELDS mapping value for '{field_name}' must be an iterable"
                    )
                for validator in value:
                    if not callable(validator):
                        raise ValueError(
                            f"Items in REQUIRED_FIELDS mapping value for '{field_name}' must be a callable validator"
                        )
        return None


class AbstractUser(AbstractBaseUser, metaclass=AbstractUserMeta):
    __abstract__ = True

    username: orm.Mapped[typing.Annotated[str, MaxLen(255)]] = orm.mapped_column(
        sa.Unicode(255),
        nullable=False,
        unique=True,
        index=True,
        doc="User's username",
    )
    password = orm.mapped_column(
        sa_utils.PasswordType(
            onload=lambda **kwargs: {
                "schemes": list(settings.get("PASSWORD_SCHEMES", ["md5_crypt"])),
                **kwargs,
            }
        ),
        nullable=False,
        doc="User's password",
    )
    is_active: orm.Mapped[bool] = orm.mapped_column(
        default=True, insert_default=True, doc="Is the user active?"
    )
    is_staff: orm.Mapped[bool] = orm.mapped_column(
        default=False, insert_default=False, doc="Is the user staff?"
    )
    is_admin: orm.Mapped[bool] = orm.mapped_column(
        default=False, insert_default=False, doc="Is the user admin?"
    )

    date_joined: orm.Mapped[datetime.datetime] = orm.mapped_column(
        sa.DateTime(timezone=True),
        default=timezone.now,
        nullable=False,
        doc="Date the user joined the system",
    )
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        sa.DateTime(timezone=True),
        default=timezone.now,
        onupdate=timezone.now,
        nullable=False,
        doc="Date the user was last updated",
    )

    USERNAME_FIELD: str = "username"
    REQUIRED_FIELDS: typing.Union[
        typing.Mapping[str, typing.List[typing.Callable]], typing.Iterable[str]
    ] = {}

    def get_username(self):
        """Return the username for the user."""
        return getattr(self, self.USERNAME_FIELD)

    @classmethod
    def _get_required_fields(cls):
        required_fields = {}
        # This is done to ensure that the username field is always the first field
        # in the required fields dictionary
        if isinstance(cls.REQUIRED_FIELDS, collections.abc.Mapping):
            required_fields[cls.USERNAME_FIELD] = cls.REQUIRED_FIELDS.get(
                cls.USERNAME_FIELD, []
            )
            required_fields.update(cls.REQUIRED_FIELDS)
            return required_fields

        required_fields[cls.USERNAME_FIELD] = []
        for field_name in cls.REQUIRED_FIELDS:
            required_fields[field_name] = []
        return required_fields

    # Override this method to customize how passwords are set
    def set_password(self, raw_password: str):
        """Set the password for the user."""
        self.password = validate_password(raw_password)

    # Override this method to customize how passwords are checked
    def check_password(self, raw_password: str) -> bool:
        """Check the password for the user."""
        return self.password == raw_password


class AnonymousUser(AbstractBaseUser):
    __abstract__ = True

    id: None = None # type: ignore

    @property
    def is_authenticated(self):
        return False

    def __init_subclass__(cls):
        raise TypeError("Cannot subclass AnonymousUser")


def get_user_model() -> typing.Type[AbstractUser]:
    auth_user_model: typing.Optional[str] = settings.AUTH_USER_MODEL
    if not auth_user_model:
        raise ValueError("AUTH_USER_MODEL is not set")

    app_name, model_name = auth_user_model.rsplit(".", maxsplit=1)

    for app in discover_apps():
        if app.name.endswith(app_name):
            for model in discover_models(app.name):
                if model.__name__ == model_name:
                    return model

    raise ValueError(f"User model '{auth_user_model}' not found")
