from typing import Type, TypeVar, Optional, Dict
import sqlalchemy as sa
import inflection
from sqlalchemy.orm import declared_attr, DeclarativeMeta, registry


mapper_registry = registry()


@mapper_registry.as_declarative_base()
class ModelBase:
    """
    Abstract base SQLAlchemy model class.
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


_Model = TypeVar("_Model", bound=ModelBase)


def get_app_name(model: Type[_Model]) -> Optional[str]:
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


def _auto_tablename(model: Type[_Model]) -> Type[_Model]:
    """Add a declarative attribute to auto-generate the table name for the model"""
    # Check if the class is mapped or already has a __tablename__
    # This is to avoid the warning thrown when hasattr(model, "__tablename__")
    # is done on a model with the __tablename__ as an already `declared_attr`
    if sa.inspect(model, raiseerr=False) is not None:
        return model

    @declared_attr
    def _tablename(model: Type[_Model]) -> str:
        app_name = get_app_name(model)
        model_name = inflection.tableize(model.__name__)

        if not app_name:
            return model_name
        return f"{app_name}__{model_name}"

    setattr(model, "__tablename__", _tablename)
    return model


class ModelBaseMeta(DeclarativeMeta):
    """Metaclass for SQLAlchemy ModelBase"""

    def __new__(meta_cls, *args, **kwargs) -> Type[_Model]:
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


class Model(
    ModelBase,
    metaclass=ModelBaseMeta,
):
    """
    Abstract base SQLAlchemy model with timestamp and UUID primary key fields

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

    id = sa.Column(
        sa.Integer,
        primary_key=True,
        index=True,
        doc="The primary key of the model",
        autoincrement=True,
    )

    @classmethod
    def get_fields(cls):
        field_mappings: Dict[str, sa.Column] = dict(cls)
        return field_mappings


_T = TypeVar("_T")
