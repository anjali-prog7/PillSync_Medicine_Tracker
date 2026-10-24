"""Expiry date parsing and status evaluation for medicine packaging.

The medicine-upload pipeline reads an expiry date (either via Gemini Vision
or from OCR text) and classifies it:

    * EXPIRED        -> the product must be shown with a RED warning
    * EXPIRING_SOON  -> within the next 90 days (yellow hint)
    * VALID          -> a normal expiry date far enough in the future
    * None           -> no expiry date was detected (never guessed)
"""

from __future__ import annotations

import datetime
import re
from typing import Optional

# A medicine expiring within this many days is flagged as "expiring soon".
EXPIRING_SOON_DAYS = 90


def parse_expiry(value) -> Optional[datetime.date]:
    """Parse a common expiry-date string into a date, or None.

    Understands the formats typically printed on Indian medicine strips /
    bottles / boxes:

        "03/2027", "03-2027", "3/27", "03.2027"
        "31/12/2026", "2026-12-31", "12/2026"
        "DEC 2026", "Dec-26", "12-26", "26" (ambiguous -> year only, Dec 31)
        "EXP 03/2027", "Expiry: 03/2027" (leading labels are stripped)

    Ambiguous 2-digit values are interpreted as MM/YY (month first), which is
    the standard on Indian pharma packaging.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Strip common labels like "EXP", "Expiry", "Use before", "Mfg/Exp".
    text = re.sub(
        r"(?i)\b(exp|expiry|exp\.?|use\s+before|expires?|best\s+before|mfg|manuf(?:actur)?ing)\b\s*[:.\-]*",
        "",
        text,
    ).strip()
    # A lone year like "2026" -> end of that year.
    if re.fullmatch(r"(19|20)\d{2}", text):
        return datetime.date(int(text), 12, 31)

    # ISO date "YYYY-MM-DD" / "YYYY/MM/DD" — must be checked before the
    # generic MM/YY pattern so "2027-01-15" is never read as 27-01-15.
    iso = re.fullmatch(r"(19|20)\d{2}[/\-.]\d{1,2}[/\-.]\d{1,2}", text)
    if iso:
        y, m, d = (int(x) for x in re.split(r"[/\-.]", iso.group(0)))
        if _valid(d, m, y):
            return datetime.date(_full_year(y), m, d)

    m = re.search(r"(\d{1,2})[/\-.](\d{2,4})(?:[/\-.](\d{2,4}))?", text)
    if not m:
        # Textual month: "DEC 2026", "Dec-26", "January 2027"
        tm = re.search(
            r"(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s./-]*(\d{2,4})",
            text,
        )
        if not tm:
            return None
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        month = months[tm.group(1).lower()[:3]]
        year_raw = tm.group(2)
        return _date_from_year(month, year_raw)

    a, b, c = m.group(1), m.group(2), m.group(3)
    if c is None:
        # MM/YY or MM/YYYY (month first is standard on pharma packaging).
        month = int(a)
        if not 1 <= month <= 12:
            return None
        return _date_from_year(month, b)

    # Three-part date: try day/month/year then year/month/day.
    candidates = [
        (int(a), int(b), int(c)),  # dd/mm/yyyy
        (int(c), int(b), int(a)),  # yyyy/mm/dd
        (int(b), int(a), int(c)),  # mm/dd/yyyy (rare on pharma)
    ]
    for d, mo, y in candidates:
        if _valid(d, mo, y):
            return datetime.date(_full_year(y), mo, d)
    return None


def _date_from_year(month: int, year_raw: str) -> Optional[datetime.date]:
    if not 1 <= month <= 12:
        return None
    year = _full_year(int(year_raw))
    # Expiry is end-of-month in the pharma world.
    if month == 12:
        return datetime.date(year, 12, 31)
    return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)


def _full_year(y: int) -> int:
    return 2000 + y if y < 100 else y


def _valid(d: int, mo: int, y: int) -> bool:
    y = _full_year(y)
    if not 1 <= mo <= 12 or d < 1:
        return False
    try:
        datetime.date(y, mo, d)
        return True
    except ValueError:
        return False


def expiry_status(value, today: Optional[datetime.date] = None) -> Optional[dict]:
    """Classify an expiry value into a status dict (or None when unknown).

    Returns::

        {
            "date": "03/2027",
            "status": "EXPIRED" | "EXPIRING_SOON" | "VALID",
            "days_left": int,
            "message": human-readable line,
        }
    """
    date = parse_expiry(value)
    if date is None:
        return None
    today = today or datetime.date.today()
    days_left = (date - today).days
    if days_left < 0:
        status = "EXPIRED"
        message = f"Medicine expired {abs(days_left)} day(s) ago ({value}). Do not use."
    elif days_left <= EXPIRING_SOON_DAYS:
        status = "EXPIRING_SOON"
        message = f"Medicine expires soon ({value}, {days_left} day(s) left)."
    else:
        status = "VALID"
        message = f"Valid until {value} ({days_left} day(s) left)."
    return {
        "date": str(value).strip(),
        "status": status,
        "days_left": int(days_left),
        "message": message,
    }
