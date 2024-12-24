import typing
from annotated_types import Ge
import sqlalchemy as sa
import inflection
from sqlalchemy import orm


mapper_registry = orm.registry()


@mapper_registry.as_declarative_base()
class ModelBase:
    """
    Declarative base for SQLAlchemy model.
    """

    def __unicode__(self) -> str:
        return "[%s(%s)]" % (
            self.__class__.__name__,
            ", ".join(
                "%s=%s" % (k, self.__dict__[k])
                for k in sorted(self.__dict__)
                if not k.startswith("_sa_")
            ),
        )


_Model = typing.TypeVar("_Model", bound=ModelBase)


def get_app_name(model: typing.Type[_Model]) -> typing.Optional[str]:
    """
    Get the name of the app in which the model is defined.

    Uses the `app_name` attribute if defined in the parent module.
    If not defined, uses the last part of the parent module name.

    Specifying `app=False` in the parent module will exclude the model from the app.

    :param model: Model class
    """
    try:
        module_name: str = model.__module__
    except AttributeError:
        # Not a class or module
        return

    parent_name = module_name.rsplit(".", maxsplit=1)[0]
    if not parent_name:
        return None

    try:
        apps_module = __import__(parent_name + ".apps", fromlist=["app_name"], level=0)
    except ModuleNotFoundError:
        return None

    return getattr(apps_module, "app_name", parent_name).rsplit(".", maxsplit=1)[-1]


def _auto_tablename(model: typing.Type[_Model]) -> typing.Type[_Model]:
    """Add a declarative attribute to auto-generate the table name for the model"""
    # Check if the class is mapped or already has a __tablename__
    # This is to avoid the warning thrown when hasattr(model, "__tablename__")
    # is done on a model with the __tablename__ as an already `declared_attr`
    if sa.inspect(model, raiseerr=False) is not None:
        return model

    @orm.declared_attr
    def _tablename(model: typing.Type[_Model]) -> str:
        app_name = get_app_name(model)
        model_name = inflection.tableize(model.__name__)

        if not app_name:
            return model_name
        return f"{app_name}__{model_name}"

    setattr(model, "__tablename__", _tablename)
    return model


class ModelBaseMeta(orm.DeclarativeMeta):
    """Metaclass for SQLAlchemy ModelBase"""

    def __new__(meta_cls, *args, **kwargs) -> typing.Type[_Model]:
        new_cls = super().__new__(meta_cls, *args, **kwargs)
        auto_tablename = bool(getattr(new_cls, "__auto_tablename__", None))
        tablename = getattr(new_cls, "__tablename__", None)

        if auto_tablename:
            if tablename is not None:
                raise ValueError(
                    f"Cannot set both `__auto_tablename__` and `__tablename__` on {new_cls}.\n "
                    "Set __auto_tablename__ to False to use a custom table name."
                )

            return _auto_tablename(new_cls)
        return new_cls

    def __iter__(meta_cls):
        if hasattr(meta_cls, "__mapper__"):
            values = meta_cls.__mapper__.columns
        else:
            values = vars(meta_cls)

        for key, value in values.items():
            if isinstance(value, sa.Column):
                yield key, value


class Model(ModelBase, metaclass=ModelBaseMeta):
    """
    Abstract base SQLAlchemy model.

    Intended to be used as a base class for all models in the application.

    Subclasses can be used as dataclasses by also inheriting from `orm.MappedAsDataclass`.

    Note: Subclasses should define the `__tablename__` attribute to specify the table name.
    or set `__auto_tablename__` to True to auto-generate the table name based on the model and app name.

    By default;
    ```python
    __tablename__ = "<app_name>__<model_name_plural>"
    ```
    """

    __abstract__ = True
    __auto_tablename__ = False
    """
    If True, the table name will be auto-generated based on the model and app name.
    Defaults to False.
    """

    id: orm.Mapped[typing.Annotated[int, Ge(0)]] = orm.mapped_column(
        primary_key=True,
        index=True,
        doc="The primary key of the model",
        autoincrement=True,
    )

    @classmethod
    def get_fields(cls):
        """
        Returns a mapping of field/column name to `orm.MappedColumn`, of the model.
        """
        field_mappings: typing.Dict[str, orm.MappedColumn] = {}
        for key, value in cls.__dict__.items():
            if isinstance(value, orm.MappedColumn):
                field_mappings[key] = value
            elif isinstance(value, sa.Column):
                mapped_column = orm.mapped_column()
                mapped_column.column = value
                field_mappings[key] = mapped_column
        return field_mappings
