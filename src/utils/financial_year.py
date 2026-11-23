"""
Financial Year Utility Module
Calculates Financial Year boundaries, codes, and ranges based on tenant configuration.
Standard defaults to Indian Financial Year (April 1 - March 31).
Supports Calendar Year (Jan 1 - Dec 31) or any custom start month.
"""

from datetime import date, datetime, timedelta
from typing import Optional, Union, Dict, Any, List
from src.utils.timezone import get_ist_now


def get_financial_year_info(
    target_date: Optional[Union[date, datetime, str]] = None,
    start_month: int = 4,
) -> Dict[str, Any]:
    """
    Computes financial year metadata for a given date and FY start month.
    """
    if target_date is None:
        target_date = get_ist_now().date()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date[:10], "%Y-%m-%d").date()
    elif isinstance(target_date, datetime):
        target_date = target_date.date()

    start_month = int(start_month or 4)
    if start_month < 1 or start_month > 12:
        start_month = 4

    y = target_date.year
    m = target_date.month

    if start_month == 1:
        start_year = y
        end_year = y
        fy_code = str(y)
        fy_label = f"CY {y}"
        fy_start_date = date(start_year, 1, 1)
        fy_end_date = date(end_year, 12, 31)
    else:
        if m >= start_month:
            start_year = y
            end_year = y + 1
        else:
            start_year = y - 1
            end_year = y
        fy_code = f"{start_year}-{end_year}"
        fy_label = f"FY {start_year}-{end_year}"
        fy_start_date = date(start_year, start_month, 1)
        next_fy_start = date(end_year, start_month, 1)
        fy_end_date = next_fy_start - timedelta(days=1)

    return {
        "fy_code": fy_code,
        "fy_label": fy_label,
        "start_year": start_year,
        "end_year": end_year,
        "start_date": fy_start_date,
        "end_date": fy_end_date,
        "start_month": start_month,
    }


def parse_financial_year_code(
    fy_input: Union[str, int],
    start_month: int = 4,
) -> Dict[str, Any]:
    """
    Parses a FY code string (e.g. '2026-2027', '2026') or integer start year into FY info.
    """
    start_month = int(start_month or 4)
    s_input = str(fy_input).strip()

    if "-" in s_input:
        parts = s_input.split("-")
        try:
            start_year = int(parts[0])
            end_year = int(parts[1])
        except (ValueError, IndexError):
            start_year = get_ist_now().year
            end_year = start_year + 1
    else:
        try:
            val = int(s_input)
            start_year = val
            end_year = val if start_month == 1 else val + 1
        except ValueError:
            start_year = get_ist_now().year
            end_year = start_year + 1

    if start_month == 1:
        fy_code = str(start_year)
        fy_label = f"CY {start_year}"
        fy_start_date = date(start_year, 1, 1)
        fy_end_date = date(start_year, 12, 31)
    else:
        fy_code = f"{start_year}-{end_year}"
        fy_label = f"FY {start_year}-{end_year}"
        fy_start_date = date(start_year, start_month, 1)
        next_fy_start = date(end_year, start_month, 1)
        fy_end_date = next_fy_start - timedelta(days=1)

    return {
        "fy_code": fy_code,
        "fy_label": fy_label,
        "start_year": start_year,
        "end_year": end_year,
        "start_date": fy_start_date,
        "end_date": fy_end_date,
        "start_month": start_month,
    }


def list_tenant_financial_years(
    start_month: int = 4,
    count_past: int = 3,
    count_future: int = 1,
) -> List[Dict[str, Any]]:
    """
    Generates a list of available financial years for dropdown filters.
    """
    current_fy = get_financial_year_info(start_month=start_month)
    curr_start_year = current_fy["start_year"]

    years = []
    # From oldest to future
    for y_offset in range(-count_past, count_future + 1):
        sy = curr_start_year + y_offset
        fy_item = parse_financial_year_code(sy, start_month=start_month)
        fy_item["is_current"] = (sy == curr_start_year)
        years.append(fy_item)

    # Sort descending by start_year (most recent first)
    years.sort(key=lambda x: x["start_year"], reverse=True)
    return years
