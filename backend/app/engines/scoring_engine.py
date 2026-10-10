"""Deterministic Mission Score for every travel mode. Formulas are documented in docs/SCORING_ENGINE.md.

Weights come from one configuration object (ScoringConfig) and are chosen by the user's priority
("What matters most?"). The AI never sees or changes them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.engines.context import MissionContext
from app.schemas.mission import Preference, Priority
from app.schemas.result import Itinerary, ScoreBreakdown, ScoreFactor
from app.utils.format import fmt_minutes, fmt_money

COMPONENTS = ("arrival", "budget", "ground", "location", "duration", "review", "convenience")

PRIORITY_WEIGHTS: dict[str, dict[str, float]] = {
    # Balanced = the default weights
    "balanced":   {"arrival": 0.30, "budget": 0.20, "ground": 0.15, "location": 0.10, "duration": 0.10,
                   "review": 0.05, "convenience": 0.10},
    "save_money": {"arrival": 0.20, "budget": 0.45, "ground": 0.00, "location": 0.10, "duration": 0.15,
                   "review": 0.00, "convenience": 0.10},
    "save_time":  {"arrival": 0.30, "budget": 0.15, "ground": 0.00, "location": 0.05, "duration": 0.40,
                   "review": 0.00, "convenience": 0.10},
    "avoid_risk": {"arrival": 0.40, "budget": 0.15, "ground": 0.15, "location": 0.10, "duration": 0.05,
                   "review": 0.05, "convenience": 0.10},
}


@dataclass
class ScoringConfig:
    profiles: dict[str, dict[str, float]] = field(default_factory=lambda: {k: dict(v) for k, v in PRIORITY_WEIGHTS.items()})
    night_before_cushion: float = 8.0
    traffic_share: float = 0.15

    @classmethod
    def from_overrides(cls, overrides: dict[str, float] | None) -> ScoringConfig:
        """SCORING_WEIGHTS overrides the balanced (default) profile."""
        config = cls()
        if overrides:
            config.profiles["balanced"] = {**config.profiles["balanced"],
                                           **{k: float(v) for k, v in overrides.items() if k in COMPONENTS}}
        return config

    def weights_for(self, priority: str) -> dict[str, float]:
        return dict(self.profiles.get(str(priority), self.profiles["balanced"]))


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# --------------------------------------------------------------------------- component curves
def arrival_curve(effective_buffer: float, required: float) -> float:
    r = max(required, 15.0)
    eb = effective_buffer
    if eb <= 0:
        return max(5.0, 30.0 + eb / 2.0)
    if eb < r:
        return 30.0 + 50.0 * eb / r
    if eb <= r + 90:
        return 80.0 + 20.0 * (eb - r) / 90.0
    if eb <= r + 180:
        return 100.0
    return 100.0 - min(15.0, (eb - r - 180.0) / 20.0)


def budget_curve(cost: float | None, budget: float) -> float | None:
    if cost is None or budget <= 0:
        return None
    q = cost / budget
    if q <= 0.70:
        return 100.0
    if q <= 1.0:
        return 100.0 - 20.0 * (q - 0.70) / 0.30
    return max(0.0, 80.0 - 300.0 * (q - 1.0))


def ground_curve(minutes: float, max_minutes: float) -> float:
    m = max(max_minutes, 1.0)
    if minutes <= 0.5 * m:
        return 100.0
    if minutes <= m:
        return 100.0 - 30.0 * (minutes - 0.5 * m) / (0.5 * m)
    return max(0.0, 70.0 - 70.0 * (minutes - m) / m)


def location_curve(distance_km: float | None) -> float | None:
    if distance_km is None:
        return None
    d = distance_km
    if d <= 1.5:
        return 100.0
    if d <= 5:
        return 100.0 - 25.0 * (d - 1.5) / 3.5
    if d <= 15:
        return 75.0 - 40.0 * (d - 5) / 10.0
    return max(10.0, 35.0 - 2.0 * (d - 15))


def hotel_curve(rating: float | None, min_rating: float) -> float:
    if rating is None:
        return 50.0
    score = _clamp(100.0 * (rating - 2.5) / 2.5)
    if rating < min_rating:
        score -= 20.0
    return _clamp(score)


def review_curve(review_count: int | None, positive_share: float | None) -> float:
    if not review_count:
        return 35.0
    volume = min(1.0, math.log10(review_count + 1) / 3.0)
    share = positive_share if positive_share is not None else 0.6
    return _clamp(100.0 * (0.4 * volume + 0.6 * share))


def duration_curve(travel_minutes: float, fastest_minutes: float) -> float:
    """Log scale: 2× the fastest option → 65, 4× → 30, 8× → 0. Keeps hour-vs-day comparisons meaningful."""
    if fastest_minutes <= 0 or travel_minutes <= fastest_minutes:
        return 100.0
    return _clamp(100.0 - 35.0 * math.log2(travel_minutes / fastest_minutes))


def convenience_curve(itin: Itinerary) -> tuple[float, list[str]]:
    """Penalties for things that make a journey harder, independent of time and money."""
    score, notes = 100.0, []
    transfers = itin.main.transfers
    if transfers:
        score -= 12 * transfers
        notes.append(f"{transfers} change{'s' if transfers > 1 else ''} of vehicle")
    dep_hour = itin.main.departure_time.hour
    if dep_hour < 5:
        score -= 15
        notes.append("Departure before 05:00")
    arr_hour = itin.main.arrival_time.hour
    if arr_hour >= 23 or arr_hour < 5:
        score -= 10
        notes.append("Arrives late at night")
    nights_in_transit = max(0, (itin.main.arrival_time.date() - itin.main.departure_time.date()).days)
    if itin.mode != "flight" and nights_in_transit:
        score -= 12 * nights_in_transit
        notes.append(f"{nights_in_transit} night{'s' if nights_in_transit > 1 else ''} on board")
    walking = itin.transit.walking_minutes if itin.transit else 0
    if walking > 20:
        score -= 8
        notes.append(f"{walking} min of walking with luggage")
    if itin.mode == "ground" and itin.main.duration_minutes > 8 * 60:
        score -= 15
        notes.append("Very long drive")
    return _clamp(score), notes


def traffic_margin(itinerary: Itinerary, share: float) -> float:
    mission_legs = [l for l in itinerary.legs if l.day == "mission"]
    base = share * sum(l.duration_minutes for l in mission_legs)
    spread = sum(max(0, (l.typical_max_minutes or l.duration_minutes) - l.duration_minutes) for l in mission_legs)
    return max(base, float(spread))


def delay_exposure(itinerary: Itinerary) -> float:
    """Minutes of buffer that delays can plausibly eat. Zero when arriving the day before."""
    if itinerary.strategy == "night_before":
        return 0.0
    if itinerary.mode == "flight" and itinerary.flight:
        flight = itinerary.flight
        exposure = 30.0 if flight.often_delayed else 0.0
        exposure += 20.0 * flight.stops
        if flight.min_layover_minutes is not None and flight.min_layover_minutes < 60:
            exposure += 15.0
        return exposure
    if itinerary.mode == "ground":
        return 0.0  # traffic range is already built into the planned departure
    # Train / bus: no live punctuality data → conservative estimate for long-distance services
    exposure = 20.0 * itinerary.main.transfers
    long_hours = (itinerary.transit.long_distance_minutes / 60) if itinerary.transit else 0
    exposure += min(60.0, 5.0 * long_hours)
    return exposure


def positive_share(itinerary: Itinerary) -> float | None:
    hotel = itinerary.hotel
    if hotel is None:
        return None
    pos = sum(a.positive for a in hotel.review_breakdown)
    neg = sum(a.negative for a in hotel.review_breakdown)
    if pos + neg > 0:
        return pos / (pos + neg)
    if hotel.rating is not None:
        return hotel.rating / 5.0
    return None


# --------------------------------------------------------------------------- engine
class ScoringEngine:
    def __init__(self, ctx: MissionContext, config: ScoringConfig | None = None) -> None:
        self.ctx = ctx
        self.config = config or ScoringConfig()

    def score(self, itin: Itinerary, fastest_travel_minutes: int | None = None,
              cheapest_cost: float | None = None) -> ScoreBreakdown:
        ctx, req = self.ctx, self.ctx.request
        factors: list[ScoreFactor] = []
        buffer = itin.arrival.buffer_minutes

        # arrival reliability
        exposure = delay_exposure(itin)
        margin = traffic_margin(itin, self.config.traffic_share)
        effective = buffer - exposure - margin
        itin.arrival.effective_buffer_minutes = int(round(effective))
        if buffer < 0:
            arrival = 0.0
            factors.append(ScoreFactor(key="late", label=f"Arrives {fmt_minutes(-buffer)} after the deadline",
                                       impact="negative"))
        else:
            arrival = arrival_curve(effective, req.min_buffer_minutes)
            if itin.strategy == "night_before":
                arrival = min(100.0, arrival + self.config.night_before_cushion)
                factors.append(ScoreFactor(key="overnight", impact="positive",
                                           label="Arrives the day before — delays can't make you late"))
            impact = "positive" if buffer >= req.min_buffer_minutes else "negative"
            factors.append(ScoreFactor(key="buffer", label=f"{buffer}-minute arrival buffer", impact=impact,
                                       detail=f"You asked for at least {req.min_buffer_minutes} minutes."))

        # budget (total trip cost): 50% fit to the budget + 50% relative to the cheapest on-time journey,
        # so a cheaper option still earns credit when everything is comfortably within budget
        budget = budget_curve(itin.cost.total, req.budget)
        if budget is not None and itin.cost.total and cheapest_cost:
            budget = 0.5 * budget + 0.5 * 100.0 * min(1.0, cheapest_cost / itin.cost.total)
        if itin.cost.total is not None:
            diff = req.budget - itin.cost.total
            factors.append(ScoreFactor(key="budget", impact="positive" if diff >= 0 else "negative",
                                       label=f"{fmt_money(abs(diff), ctx.currency)} {'under' if diff >= 0 else 'over'} budget"))
        else:
            budget = 50.0
            factors.append(ScoreFactor(key="budget", impact="neutral", label="Total cost partly unknown"))

        # ground travel on the day
        g = itin.ground_minutes_mission_day + 0.5 * itin.ground_minutes_before
        ground = ground_curve(g, req.max_ground_minutes)
        if itin.ground_minutes_mission_day > req.max_ground_minutes:
            factors.append(ScoreFactor(key="ground", impact="negative",
                                       label=f"{fmt_minutes(itin.ground_minutes_mission_day)} of ground travel on the day"))

        # location & stay (hotel distance 60% + rating 40%), review confidence
        location = review = None
        if itin.hotel is not None:
            dist = location_curve(itin.hotel.distance_km)
            rating = hotel_curve(itin.hotel.rating, req.min_hotel_rating)
            location = 0.6 * (dist if dist is not None else 40.0) + 0.4 * rating
            if itin.hotel.distance_km is not None:
                d = itin.hotel.distance_km
                factors.append(ScoreFactor(key="location", label=f"Hotel {d:.1f} km from the venue",
                                           impact="positive" if d <= 3 else "negative" if d > 8 else "neutral"))
            review = review_curve(itin.hotel.reviews, positive_share(itin))

        # travel duration (time actually travelling), relative to the quickest journey
        fastest = fastest_travel_minutes or itin.total_travel_minutes
        duration = duration_curve(itin.total_travel_minutes, fastest)

        # convenience
        convenience, notes = convenience_curve(itin)
        for note in notes:
            factors.append(ScoreFactor(key="convenience", impact="negative", label=note))
        if itin.mode == "flight" and itin.flight:
            if itin.flight.stops == 0:
                factors.append(ScoreFactor(key="direct", impact="positive", label="Direct flight"))
            if itin.flight.often_delayed:
                factors.append(ScoreFactor(key="delays", impact="negative", label="Often delayed by 30+ minutes"))
        if itin.cost.ticket_source == "estimated":
            factors.append(ScoreFactor(key="estimate", impact="neutral", label="Ticket price is an estimate"))

        components: dict[str, float | None] = {
            "arrival": arrival, "budget": budget, "ground": ground, "location": location, "duration": duration,
            "review": review, "convenience": convenience}
        weights = self.config.weights_for(req.priority)
        active = {k: w for k, w in weights.items() if components.get(k) is not None and w > 0}
        total_weight = sum(active.values()) or 1.0
        overall = sum(components[k] * w for k, w in active.items()) / total_weight  # type: ignore[operator]
        overall += self._preference_adjustment(itin, factors)
        if buffer < 0:
            overall = min(overall, 25.0)  # cannot be recommended in any case

        # value index: cost efficiency, time efficiency, reliability — used for "Best value"
        cost_eff = 0.0
        if itin.cost.total and cheapest_cost:
            cost_eff = min(1.0, cheapest_cost / itin.cost.total)
        time_eff = min(1.0, fastest / max(itin.total_travel_minutes, 1))
        value = 100 * (0.4 * cost_eff + 0.3 * time_eff + 0.3 * arrival / 100)

        return ScoreBreakdown(
            overall=int(round(_clamp(overall))), arrival=int(round(arrival)), budget=int(round(budget)),
            ground=int(round(ground)), location=None if location is None else int(round(location)),
            duration=int(round(duration)), review=None if review is None else int(round(review)),
            convenience=int(round(convenience)), value=int(round(value)),
            weights={k: round(w / total_weight, 3) for k, w in active.items()}, priority=str(req.priority),
            factors=factors)

    def _preference_adjustment(self, itin: Itinerary, factors: list[ScoreFactor]) -> float:
        prefs = set(self.ctx.request.preferences)
        delta = 0.0

        def note(points: float, label: str) -> None:
            nonlocal delta
            delta += points
            factors.append(ScoreFactor(key="preference", impact="positive" if points > 0 else "negative",
                                       label=label, detail=f"Preference adjustment {points:+.0f}"))

        if Preference.prefer_direct in prefs and itin.mode == "flight":
            direct = itin.main.stops == 0
            note(3 if direct else -3, "Matches your direct-flight preference" if direct else "Not the direct flight you prefer")
        if Preference.avoid_early_departure in prefs and itin.main.departure_time.hour < 6:
            note(-4, "Departs before 06:00")
        if Preference.night_before_preferred in prefs and itin.strategy == "night_before":
            note(4, "Arrives the night before, as you prefer")
        if itin.hotel is not None:
            if Preference.breakfast_included in prefs and any("breakfast" in a.lower() for a in itin.hotel.amenities):
                note(3, "Breakfast available")
            if Preference.free_cancellation in prefs and itin.hotel.free_cancellation:
                note(3, "Free cancellation")
        return delta


__all__ = ["COMPONENTS", "PRIORITY_WEIGHTS", "Priority", "ScoringConfig", "ScoringEngine", "arrival_curve",
           "budget_curve", "duration_curve", "ground_curve", "hotel_curve", "location_curve", "review_curve"]
