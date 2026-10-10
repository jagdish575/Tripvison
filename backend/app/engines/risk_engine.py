"""Risk engine: how can this journey go wrong? Rules documented in docs/RISK_ENGINE.md."""

from __future__ import annotations

from app.engines.context import MissionContext
from app.schemas.result import Itinerary, ReviewInsights, RiskAssessment, RiskFactor
from app.services.review_insights import key_aspect_warning
from app.utils.format import fmt_clock, fmt_minutes, fmt_money, mission_noun


class RiskEngine:
    def __init__(self, ctx: MissionContext) -> None:
        self.ctx = ctx

    @staticmethod
    def _tight_changes(itin: Itinerary) -> int | None:
        """Shortest gap (minutes) between arriving on one long-distance service and boarding the next."""
        if not itin.transit:
            return None
        services = [s for s in itin.transit.segments if s.mode != "walk" and s.depart_at and s.arrive_at]
        gaps = [int((b.depart_at - a.arrive_at).total_seconds() // 60) for a, b in zip(services, services[1:])
                if b.duration_minutes >= 90]
        tight = [g for g in gaps if g < 45]
        return min(tight) if tight else None

    def assess(self, itin: Itinerary, insights: ReviewInsights | None = None) -> RiskAssessment:
        req = self.ctx.request
        r = req.min_buffer_minutes
        b = itin.arrival.buffer_minutes
        flight = itin.flight
        noun = mission_noun(req.mission_type)
        factors: list[RiskFactor] = []
        strengths: list[str] = []
        same_day = itin.strategy == "same_day"

        def add(key, severity, points, title, detail, recommendation=None):
            factors.append(RiskFactor(key=key, severity=severity, points=points, title=title, detail=detail,
                                      recommendation=recommendation))

        # 1. arrival buffer
        if b < 0:
            add("buffer", "high", 60, f"Arrives {fmt_minutes(-b)} after your {noun} starts",
                "This journey cannot get you there on time.", "Choose an earlier departure or travel the day before.")
        elif b < 30 or b < 0.5 * r:
            add("buffer", "high", 40, f"Only {b}-minute arrival buffer",
                f"You asked for {r} minutes. One slow taxi or a late arrival makes you late.",
                "Pick a night-before option or an earlier departure.")
        elif b < r:
            add("buffer", "medium", 20, f"{b}-minute buffer — below your {r}-minute minimum",
                "Workable, but there is little room for delays.", "Leave as early as you can after arriving.")
        else:
            strengths.append(f"{b}-minute arrival buffer")

        # 2. connections / changes of vehicle
        if itin.mode == "flight" and flight is not None:
            if flight.stops:
                short = flight.min_layover_minutes is not None and flight.min_layover_minutes < 60
                via = ", ".join(l.airport for l in flight.layovers if l.airport)
                if same_day:
                    add("connection", "medium", 12 * flight.stops,
                        f"{flight.stops} connection{'s' if flight.stops > 1 else ''}{f' via {via}' if via else ''}",
                        "A delay on the first leg can cause a missed connection on the morning of your mission.",
                        "Book both legs on one ticket so the airline must rebook you.")
                    if short:
                        add("layover", "high", 25, f"Tight {flight.min_layover_minutes}-minute layover",
                            "Under an hour to change planes leaves no slack for a late first leg.",
                            "Avoid this option for a fixed-time mission.")
                else:
                    add("connection", "low", 5, f"{flight.stops} connection the day before",
                        "A missed connection still leaves the night to recover.")
                if any(l.overnight for l in flight.layovers):
                    add("overnight_layover", "medium", 10, "Overnight layover", "Sleep at an airport before your mission.")
            else:
                strengths.append("Direct flight")
        elif itin.mode in ("train", "bus", "transit"):
            changes = itin.main.transfers
            word = "train" if itin.mode == "train" else "bus" if itin.mode == "bus" else "service"
            if changes:
                tight = self._tight_changes(itin)
                long_changes = max(0, len([s for s in (itin.transit.segments if itin.transit else [])
                                          if s.mode != "walk" and s.duration_minutes >= 90]) - 1)
                local = changes - long_changes
                breakdown = (f" ({long_changes} between {word}s, {local} to local transport)"
                             if long_changes and local else "")
                add("connection", "medium" if same_day or changes > 1 else "low", 10 * changes,
                    f"{changes} change{'s' if changes > 1 else ''} of vehicle{breakdown}",
                    "Separate tickets don't protect you if the first service runs late.",
                    "Leave extra time at each change, or pick a direct service.")
                if tight:
                    add("tight_change", "medium", 10, f"Only {tight} minutes for a change",
                        "Long-distance services in India often run late; a short change is fragile.")
            else:
                strengths.append(f"Direct {word}")
            # 3. punctuality: no live running-status data for trains/buses
            long_hours = (itin.transit.long_distance_minutes / 60) if itin.transit else 0
            if long_hours >= 6:
                add("punctuality", "medium" if same_day else "low", 12 if same_day else 4,
                    f"{long_hours:.0f}+ hours on long-distance {word}s",
                    "We have the timetable but no live running status; long journeys can run late.",
                    "Check live running status on the day." if itin.mode == "train" else None)
        elif itin.mode == "ground":
            if itin.main.duration_minutes > 8 * 60:
                add("long_drive", "medium", 15, f"{fmt_minutes(itin.main.duration_minutes)} on the road",
                    "Long drives add fatigue and exposure to road delays.", "Plan rest stops; consider rail or air.")

        # 3. delay history (Google Flights 'often delayed by 30+ min')
        if flight is not None and flight.often_delayed:
            if same_day:
                add("delays", "medium", 15, "Flight is often delayed by 30+ minutes",
                    "Google Flights flags this flight's recent on-time record.",
                    "Keep the night-before alternative in mind.")
            else:
                add("delays", "low", 4, "Flight is often delayed by 30+ minutes",
                    "Arriving the day before absorbs typical delays.")

        # 4. ground transfer on the day
        g = itin.ground_minutes_mission_day
        if g > req.max_ground_minutes:
            add("ground", "high", 25, f"{fmt_minutes(g)} of ground travel on the day",
                f"Above your {req.max_ground_minutes}-minute limit.", "Choose a hotel closer to the venue.")
        elif g > 0.75 * req.max_ground_minutes:
            add("ground", "medium", 10, f"{fmt_minutes(g)} ground transfer",
                "Close to your limit — city traffic can stretch it.", "Pre-book a cab before you land.")
        spread = sum(max(0, (l.typical_max_minutes or l.duration_minutes) - l.duration_minutes)
                     for l in itin.legs if l.day == "mission")
        if spread >= 20:
            add("traffic", "low", 5, f"Traffic can add up to {spread} minutes",
                "Based on the typical travel-time range for this route.", "Leave a little earlier than planned.")

        # 5. hotel distance
        if itin.hotel is not None and itin.hotel.distance_km is not None:
            d = itin.hotel.distance_km
            if d > 10:
                add("hotel_distance", "high", 20, f"Hotel is {d:.1f} km from the venue",
                    "A long morning transfer adds avoidable risk.", "Choose a hotel within 3 km of the venue.")
            elif d > 5:
                add("hotel_distance", "medium", 10, f"Hotel is {d:.1f} km from the venue",
                    "Morning traffic makes this transfer less predictable.", "A hotel within 3 km would be safer.")
            else:
                strengths.append(f"Hotel {d:.1f} km from the venue")

        # 6. budget
        if itin.cost.total is not None:
            q = itin.cost.total / req.budget
            over = itin.cost.total - req.budget
            if q > 1.10:
                add("budget", "high", 25, f"{fmt_money(over, self.ctx.currency)} over budget",
                    f"Total {fmt_money(itin.cost.total, self.ctx.currency)} vs your {fmt_money(req.budget, self.ctx.currency)}.",
                    "Consider the cheapest option or raise the budget.")
            elif q > 1.0:
                add("budget", "medium", 12, f"{fmt_money(over, self.ctx.currency)} over budget",
                    "Slightly above what you planned to spend.")
            elif q > 0.95:
                add("budget", "low", 4, "Uses almost all of your budget",
                    "Prices can move before you book.", "Book soon.")
                strengths.append("Within budget")
            else:
                strengths.append(f"{fmt_money(-over, self.ctx.currency)} under budget")

        # 7. reviews
        if itin.hotel is not None:
            rating = itin.hotel.rating
            if rating is not None and (rating < req.min_hotel_rating or rating < 3.5):
                add("reviews", "medium", 10, f"Hotel rated {rating:.1f}",
                    f"Below your {req.min_hotel_rating:.1f} minimum." if rating < req.min_hotel_rating
                    else "Below 3.5 — guests report mixed experiences.")
            aspect = key_aspect_warning(insights)
            if aspect:
                add("review_signal", "low", 5, f"Recent reviews mention {aspect.lower()} issues",
                    "Based on the reviews returned for this hotel.")

        # 8. missing data
        missing = itin.data_quality
        if missing:
            add("missing_data", "low", min(12, 4 * len(missing)), "Some data is estimated",
                "; ".join(missing) + ".", "Treat these numbers as approximate.")
        elif all(not l.estimated for l in itin.legs):
            strengths.append("Live driving times from Google Maps")

        # 9. late arrival the evening before
        if itin.strategy == "night_before":
            arrival = itin.main.arrival_time
            word = "Flight lands" if itin.mode == "flight" else "Arrives"
            if arrival.hour >= 23 or arrival.hour < 5:
                add("late_arrival", "low", 5, f"{word} at {fmt_clock(arrival)} before your mission day",
                    "Less sleep before your mission.")
            else:
                strengths.append(f"{word} the {'evening' if arrival.hour >= 17 else 'day'} before")

        score = min(100, sum(f.points for f in factors))
        severities = {f.severity for f in factors}
        if "high" in severities or score >= 45:
            level = "HIGH"
        elif "medium" in severities or score >= 20:
            level = "MEDIUM"
        else:
            level = "LOW"

        recommendations = [f.recommendation for f in sorted(factors, key=lambda f: -f.points) if f.recommendation]
        if itin.arrival.leave_hotel_at and b >= 0:
            recommendations.insert(0, f"Leave the hotel by {fmt_clock(itin.arrival.leave_hotel_at)}.")
        factors.sort(key=lambda f: -f.points)
        return RiskAssessment(level=level, score=score, factors=factors, strengths=strengths[:6],
                              recommendations=list(dict.fromkeys(recommendations))[:4])
