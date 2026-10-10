"""Human-readable formatting used in explanations, risk factors and score factors."""

from __future__ import annotations

from datetime import datetime

_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "AED ", "SGD": "S$"}

_NOUNS = {
    "interview": "interview", "exam": "exam", "business": "meeting", "conference": "conference",
    "wedding": "wedding", "medical": "appointment", "vacation": "trip", "family": "family visit", "other": "plans",
}


def _indian_grouping(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def fmt_money(amount: float | None, currency: str = "INR") -> str:
    if amount is None:
        return "unknown"
    value = int(round(abs(amount)))
    body = _indian_grouping(value) if currency == "INR" else f"{value:,}"
    sign = "-" if amount < 0 else ""
    return f"{sign}{_SYMBOLS.get(currency, currency + ' ')}{body}"


def fmt_clock(value: datetime | None) -> str:
    return value.strftime("%H:%M") if value else "—"


def fmt_minutes(minutes: int | float | None) -> str:
    if minutes is None:
        return "—"
    m = int(round(minutes))
    if m < 60:
        return f"{m} min"
    h, rem = divmod(m, 60)
    return f"{h} h" if rem == 0 else f"{h} h {rem} min"


def mission_noun(mission_type: str) -> str:
    return _NOUNS.get(mission_type, "plans")
