from datetime import datetime, timezone
from typing import Optional, Union
import dateutil.parser


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware and converted to UTC."""
    if dt.tzinfo is None:
        # Assume UTC if naive
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_datetime_utc(val: Union[str, int, float, datetime]) -> datetime:
    """Parse various datetime representations into a timezone-aware UTC datetime.
    
    Supports ISO formats, RFC 2822 (common in RSS), Unix timestamps, and datetime objects.
    """
    if isinstance(val, datetime):
        return ensure_utc(val)
    
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)

    if isinstance(val, str):
        parsed = dateutil.parser.parse(val)
        return ensure_utc(parsed)

    raise ValueError(f"Cannot parse value of type {type(val)} to UTC datetime")
