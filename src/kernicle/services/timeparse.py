"""
Time range parsing utilities.
Converts user-friendly time specifications into journalctl-compatible formats.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
import re


@dataclass
class TimeRange:
    """Represents a parsed time range for log capture."""
    
    since_utc: datetime
    """The absolute UTC datetime for the start of the range."""
    
    since_arg: str
    """The formatted argument to pass to journalctl --since."""
    
    range_input: str
    """The original user input."""


def parse_range(range_str: str, now: Optional[datetime] = None) -> TimeRange:
    """
    Parse a time range specification.
    
    Supports two formats:
    1. Relative: "last:5m", "last:30m", "last:2h", "last:1d", "last:30s"
    2. ISO datetime: "2025-12-30T12:00:00Z" (treated as --since)
    
    Args:
        range_str: The time range string to parse
        now: Optional datetime to use as current time (for testing)
        
    Returns:
        TimeRange object with parsed information
        
    Raises:
        ValueError: If the range format is invalid
    """
    range_str = range_str.strip()
    
    # Use provided 'now' or current UTC time
    current_time = now or datetime.now(timezone.utc)
    
    # Check for relative format: last:Xu where X is number and u is unit
    relative_pattern = r"^last:(\d+)([smhd])$"
    match = re.match(relative_pattern, range_str, re.IGNORECASE)
    
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        
        # Calculate timedelta based on unit
        unit_map = {
            "s": timedelta(seconds=amount),
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
        }
        
        delta = unit_map[unit]
        since_utc = current_time - delta
        
        # Format for journalctl: ISO 8601 format
        since_arg = since_utc.strftime("%Y-%m-%d %H:%M:%S")
        
        return TimeRange(
            since_utc=since_utc,
            since_arg=since_arg,
            range_input=range_str
        )
    
    # Try to parse as ISO datetime
    try:
        # Handle both with and without 'Z' suffix
        if range_str.endswith("Z"):
            since_utc = datetime.fromisoformat(range_str[:-1]).replace(tzinfo=timezone.utc)
        else:
            # Try to parse and assume UTC if no timezone
            dt = datetime.fromisoformat(range_str)
            if dt.tzinfo is None:
                since_utc = dt.replace(tzinfo=timezone.utc)
            else:
                since_utc = dt.astimezone(timezone.utc)
        
        since_arg = since_utc.strftime("%Y-%m-%d %H:%M:%S")
        
        return TimeRange(
            since_utc=since_utc,
            since_arg=since_arg,
            range_input=range_str
        )
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Invalid time range format: '{range_str}'. "
            f"Expected 'last:Xu' (where u=s/m/h/d) or ISO datetime like '2025-12-30T12:00:00Z'"
        ) from e
