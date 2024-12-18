import typing
import sys
import getpass

import fastapi.exceptions
from helpers.fastapi import commands

from .users import get_user_model
from helpers.fastapi.sqlalchemy.setup import get_session


def capture_password(
    validators: typing.Optional[typing.List[typing.Callable]] = None,
) -> str:
    """
    Capture a password from the user.

    :return: The password.
    """
    validators = validators or []
    while True:
        password = getpass.getpass("password: ")
        confirm_password = getpass.getpass("confirm password: ")

        if password != confirm_password:
            sys.stderr.write("Passwords do not match.\n")
            sys.stderr.flush()
            continue

        try:
            for validator in validators:
                validator(password)
        except ValueError as exc:
            sys.stderr.write(f"Invalid password: {exc}\n")
            sys.stderr.flush()
        except fastapi.exceptions.ValidationException as exc:
            sys.stderr.write(f"Invalid password: {"\n".join(exc.errors())}\n")
            sys.stderr.flush()
        else:
            return password


@commands.register
def create_admin_user(username: typing.Optional[str] = None):
    """
    Create an admin instance of settings.AUTH_USER_MODEL.

    :param username: value for the username field of the instance.
    """
    user_model = get_user_model()
    kwds = {
        "is_active": True,
        "is_staff": True,
        "is_admin": True,
    }
    if username:
        kwds[user_model.USERNAME_FIELD] = username

    for field, validators in user_model._get_required_fields().items():
        if field not in kwds:
            kwds[field] = commands.capture_input(f"{field}: ", validators)

    while True:
        password = capture_password()
        user = user_model(**kwds)
        try:
            user.set_password(password)
        except ValueError as exc:
            sys.stderr.write(f"Password is invalid: {exc}\n")
            sys.stderr.flush()
        except fastapi.exceptions.ValidationException as exc:
            sys.stderr.write(f"Password is invalid: {"\n".join(exc.errors())}\n")
            sys.stderr.flush()
        else:
            break

    session = next(get_session())
    session.add(user)
    session.commit()
    sys.stdout.write(f"Admin user '{user.get_username()}' created successfully.")
    sys.stdout.flush()


__all__ = [
    "create_admin_user",
    "capture_password",
]
