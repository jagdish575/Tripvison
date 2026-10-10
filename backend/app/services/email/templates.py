"""Responsive HTML (table layout, inline styles) + plain-text emails.

Every value comes from the stored mission snapshot / result. AI text, when present, is only the already
fact-checked "why" paragraph and never replaces a structured value.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from app.utils.format import fmt_minutes, fmt_money, mission_noun

INK, MUTED, LINE, PAPER, BLUE, AMBER = "#0B1220", "#64748B", "#E2E8F0", "#F8FAFC", "#2563EB", "#F59E0B"
RISK_COLORS = {"LOW": ("#15803D", "#F0FDF4"), "MEDIUM": ("#B45309", "#FFFBEB"), "HIGH": ("#B91C1C", "#FEF2F2")}
MODE_NAMES = {"flight": "Flight", "train": "Train", "bus": "Bus", "transit": "Public transport", "ground": "Road trip"}
SOURCE_NAMES = {"live": "LIVE", "estimated": "ESTIMATED", "user_provided": "YOUR INPUT", "calculated": "CALCULATED"}


def _dt(value: str | None, fmt: str = "%H:%M") -> str:
    if not value:
        return "—"
    return datetime.fromisoformat(value).strftime(fmt)


def _date(value: str | None) -> str:
    return datetime.fromisoformat(value).strftime("%A %d %B") if value else "—"


def _risk_badge(level: str) -> str:
    fg, bg = RISK_COLORS.get(level, (INK, PAPER))
    return (f'<span style="display:inline-block;padding:3px 8px;border-radius:3px;background:{bg};color:{fg};'
            f'font-size:12px;font-weight:700;letter-spacing:.06em">{escape(level)} RISK</span>')


def _row(label: str, value: str, strong: bool = False) -> str:
    weight = "700" if strong else "500"
    return (f'<tr><td style="padding:9px 0;border-bottom:1px solid {LINE};color:{MUTED};font-size:14px">{escape(label)}</td>'
            f'<td align="right" style="padding:9px 0;border-bottom:1px solid {LINE};color:{INK};font-size:14px;'
            f'font-weight:{weight}">{value}</td></tr>')


def _button(href: str, text: str) -> str:
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0 4px"><tr>'
            f'<td style="background:{BLUE};border-radius:4px"><a href="{escape(href)}" '
            f'style="display:inline-block;padding:12px 22px;color:#fff;font-weight:600;font-size:15px;'
            f'text-decoration:none">{escape(text)}</a></td></tr></table>')


def _layout(preheader: str, eyebrow: str, title: str, body: str, footer_note: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:{PAPER};font-family:-apple-system,'Segoe UI',Inter,Arial,sans-serif;color:{INK}">
<div style="display:none;max-height:0;overflow:hidden">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border:1px solid {LINE};border-radius:8px;overflow:hidden">
<tr><td style="background:{INK};padding:22px 28px">
<table role="presentation" width="100%"><tr>
<td style="color:#fff;font-size:17px;font-weight:700;letter-spacing:-.01em">
<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{AMBER};margin-right:8px"></span>TRIPVISION</td>
<td align="right" style="color:rgba(255,255,255,.55);font-size:11px;letter-spacing:.1em;text-transform:uppercase">{escape(eyebrow)}</td>
</tr></table>
<div style="color:#fff;font-family:Georgia,'Times New Roman',serif;font-size:28px;line-height:1.2;margin-top:18px">{escape(title)}</div>
</td></tr>
<tr><td style="padding:24px 28px 8px">{body}</td></tr>
<tr><td style="padding:18px 28px 26px;color:{MUTED};font-size:12px;line-height:1.6;border-top:1px solid {LINE}">{footer_note}</td></tr>
</table></td></tr></table></body></html>"""


def _footer(view_url: str) -> str:
    return (f"Prices, schedules and traffic change — confirm before you book. TripMission doesn't book travel or "
            f"guarantee arrival. <a href=\"{escape(view_url)}\" style=\"color:{BLUE}\">Open your mission</a>.")


def _journey_rows(s: dict[str, Any]) -> str:
    cur = s.get("currency", "INR")
    rows = [
        _row("Recommended", f"{escape(MODE_NAMES.get(s['mode'], s['mode']))} · {escape(s['title'])}", True),
        _row("Mission score", f"{s['score']}/100", True),
        _row("Departure", f"{_dt(s['departure'], '%a %d %b, %H:%M')} · {escape(s['departure_label'])}"),
        _row("Arrival at venue", _dt(s["venue_arrival"])),
        _row("Required arrival", _dt(s["deadline"])),
        _row("Buffer", f"{s['buffer']} minutes"),
        _row("Risk", _risk_badge(s["risk"])),
    ]
    if s.get("total_cost") is not None:
        rows.append(_row("Total trip cost", fmt_money(s["total_cost"], cur), True))
    if s.get("budget_remaining") is not None:
        remaining = s["budget_remaining"]
        rows.append(_row("Budget remaining" if remaining >= 0 else "Over budget by", fmt_money(abs(remaining), cur)))
    if s.get("hotel"):
        rows.append(_row("Hotel", escape(s["hotel"])))
    if s.get("leave_hotel_at"):
        rows.append(_row("Leave the hotel", _dt(s["leave_hotel_at"])))
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'


def _text_lines(s: dict[str, Any]) -> list[str]:
    cur = s.get("currency", "INR")
    lines = [
        f"Recommended: {MODE_NAMES.get(s['mode'], s['mode'])} · {s['title']}",
        f"Mission score: {s['score']}/100",
        f"Departure: {_dt(s['departure'], '%a %d %b, %H:%M')} · {s['departure_label']}",
        f"Arrival at venue: {_dt(s['venue_arrival'])}",
        f"Required arrival: {_dt(s['deadline'])}",
        f"Buffer: {s['buffer']} minutes",
        f"Risk: {s['risk']}",
    ]
    if s.get("total_cost") is not None:
        lines.append(f"Total trip cost: {fmt_money(s['total_cost'], cur)}")
    if s.get("budget_remaining") is not None:
        lines.append(f"Budget remaining: {fmt_money(s['budget_remaining'], cur)}")
    return lines


# --------------------------------------------------------------------------- trip summary
def render_trip_summary(s: dict[str, Any], *, why: str | None, cost_items: list[dict[str, Any]],
                        view_url: str) -> tuple[str, str, str]:
    noun = mission_noun(s["mission_type"])
    subject = f"Your {s['destination']} journey is ready — {s['score']}/100, {s['risk'].lower()} risk"
    route = f"{s['origin']} → {s['destination']}"
    costs = ""
    if cost_items:
        cur = s.get("currency", "INR")
        cost_rows = "".join(
            _row(f"{i['label']} · {SOURCE_NAMES.get(i['source'], i['source'])}", fmt_money(i["amount"], cur))
            for i in cost_items)
        costs = (f'<p style="margin:26px 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:{MUTED}">'
                 f'TOTAL TRIP COST</p><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{cost_rows}</table>')
    why_html = (f'<p style="margin:26px 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:{MUTED}">'
                f'WHY THIS OPTION?</p><p style="margin:0;font-size:15px;line-height:1.6;color:{INK}">{escape(why)}</p>'
                if why else "")
    body = (f'<p style="margin:0 0 4px;font-size:13px;color:{MUTED}">{escape(_date(s["travel_date"] + "T00:00"))} · '
            f'{escape(noun.capitalize())} at {escape(s["venue"])}</p>'
            f'<p style="margin:0 0 18px;font-size:20px;font-weight:700">{escape(route)}</p>'
            f'{_journey_rows(s)}{costs}{why_html}{_button(view_url, "View my journey")}')
    html = _layout(f"{route}: arrive {_dt(s['venue_arrival'])} with a {s['buffer']}-minute buffer.",
                   "Trip summary", "Your journey is ready.", body, _footer(view_url))
    text = "\n".join(["TRIPVISION — Your journey is ready.", "", route, f"Mission: {noun}",
                      f"Date: {_date(s['travel_date'] + 'T00:00')}", "", *_text_lines(s), "",
                      *(["Why this option?", why, ""] if why else []), f"View my journey: {view_url}"])
    return subject, html, text


# --------------------------------------------------------------------------- reminder
def render_reminder(s: dict[str, Any], *, notes: list[str], view_url: str) -> tuple[str, str, str]:
    noun = mission_noun(s["mission_type"])
    status = ("Everything currently looks good." if s["risk"] == "LOW" and s["buffer"] >= s["required_buffer"]
              else "Please review the notes below.")
    subject = f"Reminder: your {s['destination']} {noun} — leave {_dt(s['departure'], '%a %H:%M')}"
    notes_html = "".join(f'<li style="margin:4px 0">{escape(n)}</li>' for n in notes)
    body = (f'<p style="margin:0 0 16px;font-size:16px;line-height:1.5">Your {escape(s["destination"])} mission is coming up. '
            f'{escape(status)}</p>{_journey_rows(s)}'
            + (f'<p style="margin:24px 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:{MUTED}">'
               f'IMPORTANT NOTES</p><ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.6">{notes_html}</ul>'
               if notes else "")
            + _button(view_url, "View my journey"))
    html = _layout(f"Departure {_dt(s['departure'], '%a %H:%M')} · buffer {s['buffer']} min · {s['risk']} risk",
                   "Reminder", f"Your {s['destination']} mission is coming up.", body, _footer(view_url))
    text = "\n".join([f"TRIPVISION — Your {s['destination']} mission is coming up.", status, "", *_text_lines(s), "",
                      *([f"- {n}" for n in notes]), "", f"View my journey: {view_url}"])
    return subject, html, text


# --------------------------------------------------------------------------- change alert
def _change_value(field: str, value: Any, currency: str) -> str:
    if value is None:
        return "—"
    if field in ("venue_arrival", "arrival_main"):
        return _dt(value)
    if field == "buffer":
        return f"{value} min"
    if field == "total_cost":
        return fmt_money(value, currency)
    return str(value)


def render_change_alert(before: dict[str, Any], after: dict[str, Any] | None, report: dict[str, Any], *,
                        view_url: str) -> tuple[str, str, str]:
    subject = f"Your {before['destination']} journey needs attention"
    cur = before.get("currency", "INR")
    rows = []
    text_rows = []
    for change in report["changes"]:
        if not change["meaningful"]:
            continue
        b = _change_value(change["field"], change["before"], cur)
        a = _change_value(change["field"], change["after"], cur)
        rows.append(f'<tr><td style="padding:9px 0;border-bottom:1px solid {LINE};color:{MUTED};font-size:14px">'
                    f'{escape(change["label"])}</td><td align="right" style="padding:9px 0;border-bottom:1px solid {LINE};'
                    f'font-size:14px"><span style="color:{MUTED};text-decoration:line-through">{escape(b)}</span>'
                    f' &nbsp;→&nbsp; <strong style="color:{INK}">{escape(a)}</strong></td></tr>')
        text_rows.append(f"{change['label']}: {b} → {a}")
    if report.get("journey_unavailable"):
        rows.append(f'<tr><td colspan="2" style="padding:9px 0;font-size:14px;color:#B91C1C">'
                    f'Your recommended journey is no longer available.</td></tr>')
        text_rows.append("Your recommended journey is no longer available.")
    body = (f'<p style="margin:0 0 16px;font-size:16px;line-height:1.5">We re-checked live data for your '
            f'{escape(before["origin"])} → {escape(before["destination"])} journey and something important changed.</p>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
            + (f'<p style="margin:20px 0 0;font-size:14px;color:{MUTED}">Current risk: {_risk_badge(after["risk"])}</p>'
               if after else "")
            + _button(view_url, "Review alternatives"))
    html = _layout("Your arrival, buffer or risk changed — review your options.", "Journey change",
                   "Your journey needs attention.", body, _footer(view_url))
    text = "\n".join(["TRIPVISION — Your journey needs attention.", "", *text_rows, "", f"Review alternatives: {view_url}"])
    return subject, html, text
