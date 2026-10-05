from datetime import date, datetime
import re

import pytz


PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_digits(value):
    """Convert Persian and Arabic digits to Latin digits."""

    if value in (None, False):
        return ""

    return str(value).strip().translate(
        PERSIAN_DIGITS
    )


def gregorian_to_jalali(year, month, day):
    """Convert a Gregorian date to a Jalali date."""

    gregorian_days = [
        0,
        31,
        59,
        90,
        120,
        151,
        181,
        212,
        243,
        273,
        304,
        334,
    ]

    if year > 1600:
        jalali_year = 979
        year -= 1600
    else:
        jalali_year = 0
        year -= 621

    adjusted_year = (
        year + 1
        if month > 2
        else year
    )

    days = (
        365 * year
        + (adjusted_year + 3) // 4
        - (adjusted_year + 99) // 100
        + (adjusted_year + 399) // 400
        - 80
        + day
        + gregorian_days[month - 1]
    )

    jalali_year += 33 * (
        days // 12053
    )
    days %= 12053

    jalali_year += 4 * (
        days // 1461
    )
    days %= 1461

    if days > 365:
        jalali_year += (
            days - 1
        ) // 365

        days = (
            days - 1
        ) % 365

    if days < 186:
        jalali_month = (
            1 + days // 31
        )
        jalali_day = (
            1 + days % 31
        )
    else:
        jalali_month = (
            7 + (days - 186) // 30
        )
        jalali_day = (
            1 + (days - 186) % 30
        )

    return (
        jalali_year,
        jalali_month,
        jalali_day,
    )


def jalali_to_gregorian(year, month, day):
    """Convert a Jalali date to a Gregorian date."""

    if year > 979:
        gregorian_year = 1600
        year -= 979
    else:
        gregorian_year = 621

    days = (
        365 * year
        + (year // 33) * 8
        + ((year % 33) + 3) // 4
        + 78
        + day
    )

    if month < 7:
        days += (
            month - 1
        ) * 31
    else:
        days += (
            month - 7
        ) * 30 + 186

    gregorian_year += 400 * (
        days // 146097
    )
    days %= 146097

    if days > 36524:
        gregorian_year += 100 * (
            (days - 1) // 36524
        )

        days = (
            days - 1
        ) % 36524

        if days >= 365:
            days += 1

    gregorian_year += 4 * (
        days // 1461
    )
    days %= 1461

    if days > 365:
        gregorian_year += (
            days - 1
        ) // 365

        days = (
            days - 1
        ) % 365

    gregorian_day = days + 1

    is_leap = (
        gregorian_year % 4 == 0
        and gregorian_year % 100 != 0
    ) or (
        gregorian_year % 400 == 0
    )

    month_lengths = [
        0,
        31,
        29 if is_leap else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ]

    gregorian_month = 1

    while (
        gregorian_month <= 12
        and gregorian_day
        > month_lengths[gregorian_month]
    ):
        gregorian_day -= (
            month_lengths[gregorian_month]
        )
        gregorian_month += 1

    return (
        gregorian_year,
        gregorian_month,
        gregorian_day,
    )


def format_jalali_date(value):
    """Return YYYY/MM/DD for a Gregorian date."""

    if not value:
        return False

    if isinstance(value, datetime):
        value = value.date()

    if isinstance(value, str):
        value = date.fromisoformat(
            value[:10]
        )

    year, month, day = (
        gregorian_to_jalali(
            value.year,
            value.month,
            value.day,
        )
    )

    return "%04d/%02d/%02d" % (
        year,
        month,
        day,
    )


def format_jalali_datetime(
    value,
    timezone_name="Asia/Tehran",
):
    """Return Jalali date and local time for an Odoo UTC datetime."""

    if not value:
        return False

    if isinstance(value, str):
        value = datetime.fromisoformat(
            value
        )

    if value.tzinfo is None:
        value = pytz.UTC.localize(
            value
        )

    local_value = value.astimezone(
        pytz.timezone(timezone_name)
    )

    jalali_date = format_jalali_date(
        local_value.date()
    )

    return "%s %s" % (
        jalali_date,
        local_value.strftime(
            "%H:%M:%S"
        ),
    )


def parse_jalali_date(value):
    """Parse Persian or Latin YYYY/MM/DD into a Gregorian date."""

    normalized = normalize_digits(
        value
    )

    parts = [
        item
        for item in re.split(
            r"[/\-.]+",
            normalized,
        )
        if item
    ]

    if len(parts) != 3:
        raise ValueError(
            "Jalali date must use YYYY/MM/DD format."
        )

    try:
        jalali_year = int(parts[0])
        jalali_month = int(parts[1])
        jalali_day = int(parts[2])
    except ValueError as error:
        raise ValueError(
            "Jalali date contains invalid characters."
        ) from error

    if not 1 <= jalali_month <= 12:
        raise ValueError(
            "Jalali month must be between 1 and 12."
        )

    if not 1 <= jalali_day <= 31:
        raise ValueError(
            "Jalali day must be between 1 and 31."
        )

    gregorian_values = (
        jalali_to_gregorian(
            jalali_year,
            jalali_month,
            jalali_day,
        )
    )

    gregorian_date = date(
        *gregorian_values
    )

    converted_back = (
        gregorian_to_jalali(
            gregorian_date.year,
            gregorian_date.month,
            gregorian_date.day,
        )
    )

    if converted_back != (
        jalali_year,
        jalali_month,
        jalali_day,
    ):
        raise ValueError(
            "The entered Jalali date is not valid."
        )

    return gregorian_date
