"""Date helpers — ISO normalization, DE formats."""

from __future__ import annotations

from datetime import date as _date, datetime

FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")


def parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date format: {raw!r}")


def iso_date(d: _date) -> str:
    return d.isoformat()


def today_iso() -> str:
    return _date.today().isoformat()
