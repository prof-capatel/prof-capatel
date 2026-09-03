from datetime import datetime, date, timezone, timedelta
from typing import Optional

# Indian Standard Time (IST): UTC + 5 hours 30 minutes
IST_OFFSET = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET, name="IST")


def get_ist_now() -> datetime:
    """Returns the current datetime in Indian Standard Time (naive for MySQL DATETIME compatibility)."""
    return datetime.now(IST).replace(tzinfo=None)


def get_ist_date() -> date:
    """Returns today's date in Indian Standard Time."""
    return datetime.now(IST).date()


def format_ist_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Safely formats a datetime object to an IST string."""
    if dt is None:
        return "N/A"
    return dt.strftime(fmt)
