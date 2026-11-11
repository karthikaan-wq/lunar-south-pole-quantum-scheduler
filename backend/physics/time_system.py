
from datetime import datetime, timezone

from .kernels import load_kernels


def parse_utc(text: str) -> datetime:
    """
    Parse an ISO-format UTC date/time string.

    Accepts:
        2026-11-10T00:00:00
        2026-11-10T00:00:00Z
        2026-11-10T05:30:00+05:30

    Naive timestamps are interpreted as UTC.
    Returns a timezone-aware UTC datetime.
    """
    moment = datetime.fromisoformat(
        text.strip().replace("Z", "+00:00")
    )

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return moment.astimezone(timezone.utc)


def utc_string(moment: datetime) -> str:
    """
    Convert a datetime into a SPICE-compatible UTC string.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)

    return moment.strftime("%Y-%m-%d %H:%M:%S.%f") + " UTC"


def to_et(moment: datetime) -> float:
    """
    Convert UTC datetime into SPICE Ephemeris Time (ET).
    """
    import spiceypy as spice

    load_kernels()

    return spice.str2et(utc_string(moment))


def et_to_utc(et: float) -> str:
    """
    Convert SPICE Ephemeris Time into an ISO UTC string.
    """
    import spiceypy as spice

    load_kernels()

    return spice.et2utc(et, "ISOC", 3)
