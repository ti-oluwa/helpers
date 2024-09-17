import typing
import datetime

try:
    import zoneinfo
except ImportError:
    from backports import zoneinfo


# NOTE: This is not a perfect implementation, as not all edge cases have been consider.
def split(
    start: typing.Union[datetime.date, datetime.datetime],
    end: typing.Union[datetime.date, datetime.datetime],
    part_factor: datetime.timedelta = datetime.timedelta(days=1),
    parts: typing.Optional[int] = None,
):
    """
    Generator.

    Yields date/datetime ranges by splitting a given date/datetime range into parts based on a given part factor.

    :param start: The start date/datetime of the range.
    :param end: The end date/datetime of the range.
    :param parts: The number of parts to split the date/datetime range into.
    :param part_factor: The factor to use for splitting the date/datetime range.
        Each part's size will be a multiple of this factor, except in edge case,
        where it may not. However, they cannot be smaller than this factor.
    :return: A generator that yields tuples of date/datetime ranges.
    :raises: ValueError.
    - If the start and end dates/datetimes are the same.
    - If the start date/datetime is greater than the end date/datetime.
    - If `parts` is not a positive integer.
    - If the date/datetime range is too small to split into parts based on the given part factor.
    - If the date/datetime range is too small to split into the specified number of parts based on the given part factor.

    Example:

    ```python

    start = datetime.date(2021, 1, 1)
    end = datetime.date(2021, 1, 11)

    for date_range in split(
        start, end,
        part_factor=datetime.timedelta(days=2)
    ):
        print(date_range)

    # Output:
    # (datetime.date(2021, 1, 1), datetime.date(2021, 1, 3))
    # (datetime.date(2021, 1, 3), datetime.date(2021, 1, 5))
    # (datetime.date(2021, 1, 5), datetime.date(2021, 1, 7))
    # (datetime.date(2021, 1, 7), datetime.date(2021, 1, 11)) # An edge case
    # The last range is 3 days long because the next range will not be a multiple of 2 days
    ```
    """
    if start == end:
        raise ValueError("The start and end dates/datetimes cannot be the same.")
    if start > end:
        raise ValueError(
            "The start date/datetime must be less than the end date/datetime."
        )
    if parts is not None and (not isinstance(parts, int) or parts < 1):
        raise ValueError("parts must be a positive integer.")

    # Get the range/time difference between the start and end dates/datetimes
    date_range = end - start
    # Calculate the number of possible parts based on the part factor
    possible_parts = date_range // part_factor
    if possible_parts < 1:
        raise ValueError(
            "The date/datetime range is too small to "
            "split into parts based on the given part factor."
        )

    base_part_factor = part_factor
    if parts and possible_parts != parts:
        if possible_parts < parts:
            raise ValueError(
                "The date/datetime range is too small to split into the "
                "specified number of parts based on the given part factor."
            )
        else:
            # If the possible number of parts (using the provided part factor),
            # exceeds the requested number of parts, increase the part factor
            # to its nearest multiple, i.e part_factor * 2, part_factor * 3, etc.
            # and recalculate the possible parts
            multiplier = 2
            while True:
                part_factor = base_part_factor * multiplier
                possible_parts = date_range // part_factor
                remainder = date_range % part_factor
                # If the possible parts are equal to the requested parts
                if possible_parts == parts and remainder == 0:
                    break

                if possible_parts < parts:
                    remainder_is_a_multiple_of_base_part_factor = (
                        remainder % base_part_factor == datetime.timedelta(0)
                    )
                    if remainder_is_a_multiple_of_base_part_factor:
                        possible_parts += 1
                        if possible_parts == parts:
                            break

                    raise ValueError(
                        "The date/datetime range is too small to split "
                        "into the specified number of parts, using on the given part factor. "
                        "Consider reducing the number of parts, providing a larger date/datetime range, "
                        "or changing the part factor."
                    )
                # Possible parts is still greater than the required number of parts
                # Increase the multiplier and try again
                multiplier += 1

    # Start splitting the date/datetime range
    # Start with the start being the lower boundary of the first part
    lower_boundary = start
    # The upper boundary of the first part is unknown at this point
    upper_boundary = None
    for _ in range(possible_parts):
        # Calculate the upper boundary of the current part
        upper_boundary = lower_boundary + part_factor

        remainder = end - upper_boundary
        # If the difference between the end date/datetime and the upper boundary is less than the part factor
        if remainder < part_factor:
            remainder_is_a_multiple_of_base_part_factor = (
                remainder % base_part_factor == datetime.timedelta(0)
            )
            if remainder_is_a_multiple_of_base_part_factor:
                # If the remainder is a multiple of the base part factor,
                # yield the current lower boundary and next,
                # yield the current upper boundary (as the new lower boundary)
                # and the end date/datetime (as the upper boundary)
                yield (lower_boundary, upper_boundary)
                if upper_boundary != end:
                    yield (upper_boundary, end)

            else:
                # yield the current lower boundary and
                # the end date/datetime as the upper boundary
                yield (lower_boundary, end)
            # Break the loop as the date/datetime range has been fully split
            break
        else:
            # Otherwise, yield the current lower boundary and the current (calculated) upper boundary
            yield (lower_boundary, upper_boundary)

        # The next lower boundary is the current upper boundary
        lower_boundary = upper_boundary


def timedelta_code_to_timedelta(timedelta_code: str):
    """
    Parses the timedelta code into a timedelta object.

    A timedelta code is a string that represents a time period.
    The code is a number followed by a letter representing the unit of time.
    The following are the valid units of time:
    - D: Days
    - W: Weeks
    - M: Months
    - Y: Years

    The following are the valid timedelta codes:
    - 5D: 5 Days
    - 1W: 1 Week,
    - YTD: Year to Date (365 Days), etc.

    :param timedelta_code: The timedelta code to parse.
    :return: The timedelta object.
    :raises ValueError: If the timedelta code is invalid.

    Example:

        ```python
        timedelta_code_to_timedelta("5D")

        # Output:
        # datetime.timedelta(days=5)
        ```
    """
    if timedelta_code == "YTD":
        return datetime.timedelta(days=365)

    number, unit = timedelta_code[:-1], timedelta_code[-1]
    if not number.isdigit():
        raise ValueError("Invalid timedelta code")

    number = float(number)
    if unit.upper() == "D":
        return datetime.timedelta(days=number)
    elif unit.upper() == "W":
        return datetime.timedelta(weeks=number)
    elif unit.upper() == "M":
        return datetime.timedelta(days=number * 30)
    elif unit.upper() == "Y":
        return datetime.timedelta(days=number * 365)
    else:
        raise ValueError("Invalid timedelta code")


def timedelta_code_to_datetime_range(
    timdelta_code: str, *, timezone: str = None, future: bool = False
) -> typing.Tuple[typing.Optional[datetime.datetime], datetime.datetime]:
    """
    Parses the timedelta code into a datetime range.

    By default, the datetime range is calculated for the past.
    To calculate the datetime range for the future, set future to True.

    :param timdelta_code: The timedelta code to parse.
    :param timezone: The timezone to use for the datetime objects.
    :param future: Whether to calculate the datetime range for the future.
    :return: A tuple containing the start and end datetime objects.

    Example:

        ```python
        timedelta_code_to_datetime_range("5D") # 5 Days in the past

        # Output:
        # (datetime.datetime(2021, 9, 2, 10, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='UTC')), datetime.datetime(2021, 9, 7, 10, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='UTC')))

        timedelta_code_to_datetime_range("5D", timezone="Africa/Nairobi", future=True) # 5 Days in the future

        # Output:
        # (datetime.datetime(2021, 9, 7, 13, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='Africa/Nairobi')), datetime.datetime(2021, 9, 12, 13, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo(key='Africa/Nairobi')))
        ```
    """
    delta = timedelta_code_to_timedelta(timdelta_code)
    tz = zoneinfo.ZoneInfo(timezone) if timezone else None
    now = datetime.datetime.now().astimezone(tz)

    if future:
        start = now
        end = now + delta
    else:
        start = now - delta
        end = now
    return start, end
