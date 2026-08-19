"""
Time and Temporal Math Utilities for Guardian AI
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

def parse_iso(ts_str: str) -> datetime:
    """Parse ISO formatted timestamp string into datetime."""
    if not ts_str:
        return datetime.now(timezone.utc)
    ts_str = ts_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        # Handle time-only format like '14:30' or '2026-08-19 14:30:00'
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
            try:
                dt = datetime.strptime(ts_str, fmt)
                if fmt in ("%H:%M:%S", "%H:%M"):
                    today = datetime.now()
                    return dt.replace(year=today.year, month=today.month, day=today.day)
                return dt
            except ValueError:
                continue
        return datetime.now()

def get_minute_of_day(dt: datetime) -> int:
    """Returns minute of the day (0 - 1439)."""
    return dt.hour * 60 + dt.minute

def time_difference_minutes(t1_str: str, t2_str: str) -> float:
    """Returns signed difference (t2 - t1) in minutes."""
    dt1 = parse_iso(t1_str)
    dt2 = parse_iso(t2_str)
    return (dt2 - dt1).total_seconds() / 60.0

def temporal_overlap_score(current_ts_str: str, start_ts_str: str, end_ts_str: str) -> Tuple[float, float, str]:
    """
    Evaluates temporal relationship between a current timestamp and an event window.
    Returns:
      (explanation_score: 0-100, mismatch_score: 0-100, reason: str)
    """
    curr = parse_iso(current_ts_str)
    start = parse_iso(start_ts_str)
    end = parse_iso(end_ts_str)

    # 1. During the event
    if start <= curr <= end:
        return (85.0, 5.0, "Current time directly overlaps scheduled event")

    # 2. Pre-event arrival window (within 60 mins before start)
    if curr < start:
        mins_before = (start - curr).total_seconds() / 60.0
        if mins_before <= 60.0:
            # 85 down to 60 as mins increase
            score = 60.0 + (25.0 * (1.0 - (mins_before / 60.0)))
            return (round(score, 1), 10.0, f"Arrived {int(mins_before)}m before scheduled event start")
        else:
            return (20.0, 30.0, f"Arrived {int(mins_before)}m well in advance of event")

    # 3. Post-event linger window
    mins_after = (curr - end).total_seconds() / 60.0
    if mins_after <= 30.0:
        # Mild post-event buffer (crowd dispersal)
        return (70.0, 20.0, f"Event concluded {int(mins_after)}m ago (normal dispersal window)")
    elif mins_after <= 75.0:
        # Increasing mismatch
        mismatch = 30.0 + (40.0 * ((mins_after - 30.0) / 45.0))
        return (40.0, round(mismatch, 1), f"Event concluded {int(mins_after)}m ago; lingering observed")
    else:
        # Strong mismatch (> 75 min after event ended)
        mismatch = min(95.0, 70.0 + (25.0 * min(1.0, (mins_after - 75.0) / 60.0)))
        return (10.0, round(mismatch, 1), f"Event concluded {int(mins_after)}m ago; prolonged stay far beyond event end")
