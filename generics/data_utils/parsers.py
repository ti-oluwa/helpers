import re
import datetime


def cleanString(value: str) -> str:
    """Clean a string by removing leading and trailing whitespaces."""
    if not value:
        return ""
    return value.strip()


def toCamelCase(snake_str: str) -> str:
    """
    Convert a snake_case string to camelCase.

    :param snake_str: The snake_case string to convert.
    :return: The camelCase string.
    """
    if not snake_str:
        return snake_str
    components = snake_str.split("_")
    if len(components) == 1:
        return components[0]
    return components[0] + "".join(x.title() for x in components[1:])


def covertAnsToBool(value: str) -> bool:
    """Convert a string 'Yes' or 'No' to a boolean value."""
    if not value:
        return False
    return value.lower() == "yes"


def strToDateTime(
    value: str, *, format: str = "%Y-%m-%dT%H:%M:%S.%fZ"
) -> datetime.datetime | None:
    """Converts datetime string in the specified format to a datetime.datetime object"""
    if not value:
        return None
    try:
        dt_object = datetime.datetime.strptime(value, format).astimezone()
        return dt_object
    except ValueError:
        return None


def strToDate(value: str, *, format="%Y-%m-%d") -> datetime.date | None:
    """Converts datetime/date string in the specified format to a datetime.date object"""
    if not value:
        return None
    try:
        date_object = datetime.datetime.strptime(value, format).date()
        return date_object
    except ValueError:
        return None


standard_duration_re = re.compile(
    r"^"
    r"(?:(?P<days>-?\d+) (days?, )?)?"
    r"(?P<sign>-?)"
    r"((?:(?P<hours>\d+):)(?=\d+:\d+))?"
    r"(?:(?P<minutes>\d+):)?"
    r"(?P<seconds>\d+)"
    r"(?:[.,](?P<microseconds>\d{1,6})\d{0,6})?"
    r"$"
)

# Support the sections of ISO 8601 date representation that are accepted by
# timedelta
iso8601_duration_re = re.compile(
    r"^(?P<sign>[-+]?)"
    r"P"
    r"(?:(?P<days>\d+([.,]\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+([.,]\d+)?)H)?"
    r"(?:(?P<minutes>\d+([.,]\d+)?)M)?"
    r"(?:(?P<seconds>\d+([.,]\d+)?)S)?"
    r")?"
    r"$"
)

# Support PostgreSQL's day-time interval format, e.g. "3 days 04:05:06". The
# year-month and mixed intervals cannot be converted to a timedelta and thus
# aren't accepted.
postgres_interval_re = re.compile(
    r"^"
    r"(?:(?P<days>-?\d+) (days? ?))?"
    r"(?:(?P<sign>[-+])?"
    r"(?P<hours>\d+):"
    r"(?P<minutes>\d\d):"
    r"(?P<seconds>\d\d)"
    r"(?:\.(?P<microseconds>\d{1,6}))?"
    r")?$"
)


def parse_duration(value):
    """Parse a duration string and return a datetime.timedelta.

    The preferred format for durations in Django is '%d %H:%M:%S.%f'.

    Also supports ISO 8601 representation and PostgreSQL's day-time interval
    format.

    Extracted from Django's django.utils.dateparse module.
    """
    match = (
        standard_duration_re.match(value)
        or iso8601_duration_re.match(value)
        or postgres_interval_re.match(value)
    )
    if match:
        kw = match.groupdict()
        sign = -1 if kw.pop("sign", "+") == "-" else 1
        if kw.get("microseconds"):
            kw["microseconds"] = kw["microseconds"].ljust(6, "0")
        kw = {k: float(v.replace(",", ".")) for k, v in kw.items() if v is not None}
        days = datetime.timedelta(kw.pop("days", 0.0) or 0.0)
        if match.re == iso8601_duration_re:
            days *= sign
        return days + sign * datetime.timedelta(**kw)
