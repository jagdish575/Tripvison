"""MissionEngine — orchestrates live data acquisition, the shortlisting funnel, itinerary building,
scoring, risk, categorisation, review signals, local discovery and the explanation."""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.core.logging import get_logger
from app.engines.context import JourneyAssumptions, MissionContext
from app.engines.itinerary_engine import ItineraryEngine
from app.engines.risk_engine import RiskEngine
from app.engines.scoring_engine import ScoringConfig, ScoringEngine, hotel_curve, location_curve
from app.integrations.serpapi.client import CallTracker, SerpApiError
from app.schemas.mission import AccessibilityNeed, MissionRequest
from app.schemas.result import (ConstraintCheck, DataSources, FunnelStats, Itinerary, MethodNote, MissionResult,
                                MissionSummary, ModeSummary, OptionDelta, PlaceGroup, ReviewInsights, RoutePlan,
                                Suggestion, Tradeoff, VenueInfo)
from app.schemas.travel import (NormalizedFlight, NormalizedHotel, NormalizedReview, NormalizedRoute,
                                NormalizedTransit, ReportedTransportRoute, ResolvedLocation)
from app.services.airports import AIRPORTS
from app.services.explanation import AIExplainer, explain_recommendation
from app.services.geo import estimate_drive_minutes, estimate_route, haversine_km, ROAD_FACTOR
from app.services.location_resolution import LocationResolutionService
from app.services.providers import TravelDataProvider
from app.services.route_intelligence import RouteIntelligenceService
from app.services.review_insights import build_insights
from app.utils.format import fmt_clock, fmt_minutes, fmt_money, mission_noun

log = get_logger(__name__)

ProgressCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]

STAGES = ("resolve", "flights", "arrival", "hotels", "ground", "scoring", "reviews", "places", "explain")

# User-facing messages for degraded (optional or partially failed) data. Never include provider names,
# HTTP details or exception text — those go to `diagnostics` when DEBUG_MODE=true.
DEGRADED_MESSAGES: dict[str, str] = {
    "flights": "Live flight prices couldn't be loaded right now, so we compared the other ways to get there.",
    "transit": "Train and bus schedules couldn't be loaded right now — other travel options are still compared.",
    "road": "Live road routing wasn't available, so road travel isn't included this time.",
    "hotels": "Hotel prices couldn't be loaded for one of the dates, so some journeys are missing a stay.",
    "routes": "Some transfer times are estimated from distance because live route data was unavailable.",
    "reviews": "Recent hotel reviews couldn't be loaded, so hotel scores use ratings only.",
    "places": "Some local recommendations are temporarily unavailable.",
}

# slug, search query, section label, why it matters for this mission
PLACE_PLANS: dict[str, list[tuple[str, str, str, str]]] = {
    "interview": [("cafe", "cafe", "Cafés to wait in", "A calm table to review your notes before you go in."),
                  ("pharmacy", "pharmacy", "Pharmacies", "For a headache tablet or anything you forgot to pack."),
                  ("restaurant", "breakfast restaurant", "Breakfast nearby", "Eat properly before a long day.")],
    "exam": [("cafe", "cafe", "Cafés to wait in", "Somewhere quiet for a last revision."),
             ("stationery", "stationery shop", "Stationery", "Spare pens, pencils and printouts of your admit card."),
             ("pharmacy", "pharmacy", "Pharmacies", "In case you need anything before the exam.")],
    "business": [("coworking", "coworking space", "Coworking spaces", "A desk and Wi-Fi to prepare or take a call."),
                 ("cafe", "cafe", "Cafés", "For an informal pre-meeting."),
                 ("restaurant", "restaurant", "Restaurants", "For a client lunch afterwards.")],
    "conference": [("coworking", "coworking space", "Coworking spaces", "Somewhere to work between sessions."),
                   ("cafe", "cafe", "Cafés", "Coffee before the keynote."),
                   ("restaurant", "restaurant", "Restaurants", "For dinner with other attendees.")],
    "medical": [("pharmacy", "pharmacy", "Pharmacies", "Fill prescriptions right after the appointment."),
                ("restaurant", "restaurant", "Places to eat", "A light meal before or after."),
                ("atm", "atm", "ATMs", "Some clinics prefer cash payments.")],
    "wedding": [("salon", "salon", "Salons", "Last-minute grooming before the ceremony."),
                ("gift", "gift shop", "Gift shops", "Pick up a present on the way."),
                ("restaurant", "restaurant", "Restaurants", "For the days around the event.")],
    "vacation": [("attraction", "tourist attraction", "Things to see", "Highly rated sights close to your base."),
                 ("restaurant", "restaurant", "Restaurants", "Well-reviewed places to eat."),
                 ("viewpoint", "scenic viewpoint", "Photography spots", "Views worth the detour.")],
    "family": [("restaurant", "family restaurant", "Family restaurants", "Easy meals for everyone."),
               ("park", "park", "Parks", "Space for kids to unwind after travel."),
               ("pharmacy", "pharmacy", "Pharmacies", "Travelling with family — good to know where one is.")],
    "other": [("restaurant", "restaurant", "Restaurants", "Well-reviewed places to eat."),
              ("cafe", "cafe", "Cafés", "Somewhere to wait comfortably."),
              ("pharmacy", "pharmacy", "Pharmacies", "In case you need anything.")],
}


@dataclass
class EngineArtifacts:
    flights: list[tuple[NormalizedFlight, str, bool]] = field(default_factory=list)
    hotels: list[tuple[NormalizedHotel, date, date, bool]] = field(default_factory=list)
    reviews: dict[str, list[NormalizedReview]] = field(default_factory=dict)
    transit: list[tuple[NormalizedTransit, bool]] = field(default_factory=list)
    ground: NormalizedRoute | None = None
    itineraries: list[Itinerary] = field(default_factory=list)
    origin_code: str | None = None
    destination_code: str | None = None


async def resolve_locations(request: MissionRequest, provider: TravelDataProvider, settings: Settings,
                            tracker: CallTracker | None = None) -> tuple[ResolvedLocation, ResolvedLocation]:
    """Validation is "can we resolve this place?" — never "does it have an airport?"."""
    service = LocationResolutionService(settings, provider, tracker)
    origin = await service.resolve(request.origin, field="origin")
    destination = await service.resolve(request.destination, field="destination")
    if origin.city.casefold() == destination.city.casefold() or haversine_km(origin.location,
                                                                              destination.location) < 3:
        raise ValidationAppError("Origin and destination are the same place.",
                                 code="same_origin_destination", details={"field": "destination"})
    return origin, destination


_SERVICE_NUMBER = re.compile(r"\b(\d{4,5})\b")
FARE_MATCH_MINUTES = 10  # a reported route departing within this of a Maps service is the same service


def _long_services(option: NormalizedTransit):
    return [seg for seg in option.segments if seg.mode in ("train", "bus") and seg.duration_minutes >= 45]


def match_reported_route(option: NormalizedTransit, routes: list[ReportedTransportRoute]
                         ) -> ReportedTransportRoute | None:
    """The Google Search route that is clearly the same journey as a Google Maps transit option:
    identical service numbers (e.g. train 12919), or — when numbers are missing — the same mode, the same
    number of changes and a first departure within FARE_MATCH_MINUTES. Anything less is not a match."""
    services = _long_services(option)
    if not services:
        return None
    numbers = {n for seg in services for n in _SERVICE_NUMBER.findall(seg.name)}
    first = services[0].depart_at
    for route in routes:
        if route.fare is None or (route.mode and route.mode != option.mode):
            continue
        if numbers and route.numbers:
            if numbers == set(route.numbers):
                return route
            continue
        if first is None or route.depart_clock is None:
            continue
        gap = abs((first.hour * 60 + first.minute) - (route.depart_clock[0] * 60 + route.depart_clock[1]))
        gap = min(gap, 1440 - gap)
        changes_ok = route.changes is None or route.changes == max(0, len(services) - 1)
        if route.mode == option.mode and gap <= FARE_MATCH_MINUTES and changes_ok:
            return route
    return None


def attach_reported_fares(options: list[NormalizedTransit], routes: list[ReportedTransportRoute],
                          currency: str) -> int:
    """Replace missing fares with the fare Google Search shows for the matching route (same currency only —
    fares are never converted). Returns how many options got a reported fare."""
    usable = [r for r in routes if r.fare is not None and r.currency == currency]
    matched = 0
    for option in options:
        if option.fare is not None:
            continue
        route = match_reported_route(option, usable)
        if route is None:
            continue
        option.fare, option.currency = route.fare, route.currency
        option.fare_source = "google_search_transport_options"
        option.fare_seller = route.sellers[0] if route.sellers else None
        matched += 1
    return matched


class MissionEngine:
    def __init__(self, provider: TravelDataProvider, settings: Settings, *,
                 scoring_config: ScoringConfig | None = None, ai_explainer: AIExplainer | None = None,
                 progress: ProgressCallback | None = None) -> None:
        self.provider = provider
        self.settings = settings
        self.scoring_config = scoring_config or ScoringConfig.from_overrides(settings.scoring_weights)
        self.ai_explainer = ai_explainer
        self._progress = progress
        self.tracker = CallTracker()
        self.warnings: list[str] = []
        self.degraded: list[str] = []      # keys of DEGRADED_MESSAGES
        self.debug_notes: list[str] = []   # raw details, exposed only with DEBUG_MODE=true
        self.funnel = FunnelStats()
        self.artifacts = EngineArtifacts()
        self._hotel_prescore: dict[str, float] = {}

    async def _emit(self, stage: str, message: str, **counts: Any) -> None:
        if self._progress:
            await self._progress(stage, message, counts)

    def _warn(self, message: str) -> None:
        """A user-facing, already-friendly message."""
        if message not in self.warnings:
            self.warnings.append(message)

    def _degrade(self, key: str, detail: str = "") -> None:
        """Record degraded data: the friendly message is shown, the raw detail only in DEBUG_MODE."""
        if key not in self.degraded:
            self.degraded.append(key)
        if detail:
            self.debug_notes.append(f"{key}: {detail}")

    async def _optional(self, awaitable, key: str):
        """Run an optional lookup with a short timeout. Failures never block the mission."""
        try:
            return await asyncio.wait_for(awaitable, timeout=self.settings.optional_timeout_seconds)
        except (asyncio.TimeoutError, SerpApiError) as exc:
            self._degrade(key, getattr(exc, "code", "timeout"))
            return None

    # =================================================================== run
    async def run(self, mission_id: str, request: MissionRequest,
                  resolved: tuple[ResolvedLocation, ResolvedLocation] | None = None) -> MissionResult:
        self._places_task: asyncio.Task | None = None
        try:
            return await self._run(mission_id, request, resolved)
        finally:
            if self._places_task is not None and not self._places_task.done():
                self._places_task.cancel()

    async def _run(self, mission_id: str, request: MissionRequest,
                   resolved: tuple[ResolvedLocation, ResolvedLocation] | None) -> MissionResult:
        s = self.settings

        # ---------------------------------------------------------- 1. resolve places, venue and route plan
        await self._emit("resolve", f"Locating {request.venue or request.destination}")
        origin, destination = resolved or await resolve_locations(request, self.provider, s, self.tracker)
        venue = await self._resolve_venue(request, destination)
        assumptions = JourneyAssumptions(
            airport_exit_minutes=s.airport_exit_minutes, hotel_stop_minutes=s.hotel_stop_minutes,
            night_before_extra_margin_minutes=s.night_before_extra_margin_minutes,
            taxi_base_fare=s.taxi_base_fare, taxi_per_km=s.taxi_per_km,
            train_fare_per_km=s.train_fare_per_km, bus_fare_per_km=s.bus_fare_per_km,
            outstation_cab_per_km=s.outstation_cab_per_km, airport_checkin_minutes=s.airport_checkin_minutes)
        plan = RouteIntelligenceService(s, max_practical_drive_minutes=assumptions.max_practical_drive_minutes).plan(
            origin, destination, venue.location, [str(m) for m in request.modes])
        flying = plan.flight == "searched"
        ctx = MissionContext(
            request=request, origin=origin, destination=destination, venue=venue, assumptions=assumptions,
            origin_airport=AIRPORTS.get(plan.origin_airport.code) if flying and plan.origin_airport else None,
            destination_airport=AIRPORTS.get(plan.destination_airport.code)
            if flying and plan.destination_airport else None,
            plan=plan)
        self.artifacts.origin_code = ctx.origin_airport.code if ctx.origin_airport else None
        self.artifacts.destination_code = ctx.destination_airport.code if ctx.destination_airport else None
        builder = ItineraryEngine(ctx)
        # Local discovery only depends on the venue — run it alongside everything else.
        places_task = self._places_task = asyncio.create_task(self._places(ctx))

        # ---------------------------------------------------------- 2. flights + trains/buses + road, in parallel
        modes = set(plan.modes_evaluated)
        want_flight = flying and ctx.origin_airport is not None and ctx.destination_airport is not None
        want_transit, want_ground = bool(modes & {"train", "bus"}), "ground" in modes and plan.ground_search
        await self._emit("flights", f"Comparing {self._mode_words(modes)} from {origin.city} to {destination.city}")

        async def _value(value):
            return value

        flight_res, transit_res, ground_res = await asyncio.gather(
            self._search_flights(ctx) if want_flight else _value(([], [])),
            self._search_transit(ctx, modes) if want_transit else _value([]),
            self._search_ground(ctx) if want_ground else _value(None),
            return_exceptions=True)
        flight_error: SerpApiError | None = None
        if isinstance(flight_res, BaseException):
            if not isinstance(flight_res, SerpApiError):
                raise flight_res
            flight_error, flight_res = flight_res, ([], [])
            self._degrade("flights", flight_error.code)
        for res in (transit_res, ground_res):
            if isinstance(res, BaseException):
                raise res
        same_day_raw, before_raw = flight_res
        transit_all: list[NormalizedTransit] = transit_res  # type: ignore[assignment]
        ground_route: NormalizedRoute | None = ground_res  # type: ignore[assignment]
        if flight_error and not transit_all and ground_route is None:
            raise flight_error
        self._record_hubs(plan, transit_all)
        all_flights = {f.id: f for f in [*same_day_raw, *before_raw]}
        self.funnel.flights_found = len(all_flights)
        self.funnel.transit_found = len(transit_all)
        await self._emit("flights", f"{len(all_flights) + len(transit_all) + (1 if ground_route else 0)} travel options found",
                         flights=len(all_flights), transit=len(transit_all))

        # ---------------------------------------------------------- 3. arrival feasibility + shortlist
        await self._emit("arrival", "Checking which options arrive in time")
        arrival_airport = ctx.destination_airport
        est_airport_venue = self._estimate_minutes(arrival_airport.location, venue.location) if arrival_airport else 0
        sd_candidates, nb_candidates, relaxed_stop_ok = self._classify_flights(
            ctx, builder, list(all_flights.values()), est_airport_venue)
        self.funnel.flights_feasible = len(sd_candidates) + len(nb_candidates)
        earliest_arrival = self._earliest_venue_arrival(ctx, builder, list(all_flights.values()), est_airport_venue)
        sd_short = self._shortlist_same_day(ctx, sd_candidates, est_airport_venue)
        nb_short = self._shortlist_night_before(nb_candidates)
        self.funnel.flights_shortlisted = len(sd_short) + len(nb_short)
        short_ids = {f.id for f in [*sd_short, *nb_short]}
        for flight in all_flights.values():
            strategy = builder.strategy_for(flight) or "other"
            self.artifacts.flights.append((flight, strategy, flight.id in short_ids))
        transit_sd, transit_nb = self._classify_transit(builder, transit_all, modes)
        transit_ids = {o.id for o in [*transit_sd, *transit_nb]}
        self.artifacts.transit = [(o, o.id in transit_ids) for o in transit_all]
        self.artifacts.ground = ground_route
        ground_ok_route = self._practical_ground(ctx, ground_route)
        self.funnel.flights_feasible += len(transit_sd) + len(transit_nb) + (1 if ground_ok_route else 0)
        await self._emit("arrival", f"{self.funnel.flights_feasible} options can get you there · {len(short_ids)} flights shortlisted",
                         flights_feasible=self.funnel.flights_feasible, shortlisted=len(short_ids) + len(transit_sd) + len(transit_nb))

        # ---------------------------------------------------------- 4. hotels
        sd_hotels: list[NormalizedHotel] = []
        nb_hotels: list[NormalizedHotel] = []
        hotel_errors: list[SerpApiError] = []
        relaxed_rating = False
        need_sd_hotels = request.hotel_required and bool(sd_short or transit_sd or ground_ok_route)
        need_nb_hotels = bool(nb_short or transit_nb)
        if need_nb_hotels or need_sd_hotels:
            await self._emit("hotels", f"Finding hotels near {venue.name}")
            stays: list[tuple[str, date, date]] = []
            nights = timedelta(days=request.stay_nights)
            if need_nb_hotels:
                stays.append(("night_before", ctx.day_before, ctx.day_before + nights))
            if need_sd_hotels:
                stays.append(("same_day", ctx.mission_date, ctx.mission_date + nights))
            query = (f"hotels near {request.venue}, {destination.city}" if request.venue and venue.resolved
                     else f"hotels in {destination.city}")
            results = await asyncio.gather(*[
                self.provider.search_hotels(query, cin, cout, adults=request.travelers,
                                            min_rating=request.min_hotel_rating, currency=ctx.currency,
                                            tracker=self.tracker, purpose=f"hotels ({label.replace('_', ' ')})")
                for label, cin, cout in stays], return_exceptions=True)
            for (label, cin, cout), res in zip(stays, results):
                if isinstance(res, BaseException):
                    if not isinstance(res, SerpApiError):
                        raise res
                    hotel_errors.append(res)
                    self._degrade("hotels", f"{cin:%d %b}: {res.code}")
                    continue
                self.funnel.hotels_found += len(res)
                shortlisted, relaxed = self._shortlist_hotels(ctx, res)
                relaxed_rating = relaxed_rating or relaxed
                ids = {h.id for h in shortlisted}
                for hotel in res:
                    self.artifacts.hotels.append((hotel, cin, cout, hotel.id in ids))
                if label == "night_before":
                    nb_hotels = shortlisted
                else:
                    sd_hotels = shortlisted
            self.funnel.hotels_shortlisted = len({h.id for h in [*sd_hotels, *nb_hotels]})
            if relaxed_rating:
                self._warn(f"No hotel met your {request.min_hotel_rating:.1f}★ minimum — showing the best available.")
            await self._emit("hotels", f"{self.funnel.hotels_found} hotels found · {self.funnel.hotels_shortlisted} shortlisted",
                             hotels=self.funnel.hotels_found, hotels_shortlisted=self.funnel.hotels_shortlisted)

        # ---------------------------------------------------------- 5. ground travel
        await self._emit("ground", "Calculating transfers to your venue")
        routes = await self._compute_routes(ctx, need_airport_venue=bool(sd_short) and not request.hotel_required,
                                            hotels=[*nb_hotels, *sd_hotels])
        await self._emit("ground", f"{self.funnel.routes_calculated} routes calculated",
                         routes=self.funnel.routes_calculated)

        # ---------------------------------------------------------- 6. build, score, risk
        await self._emit("scoring", "Scoring complete journeys")
        itineraries = self._build_all(builder, ctx, sd_short, nb_short, sd_hotels, nb_hotels, routes)
        itineraries += self._build_transit_and_ground(builder, ctx, transit_sd, transit_nb, ground_ok_route,
                                                      sd_hotels, nb_hotels, routes)
        if not itineraries and hotel_errors and (need_nb_hotels or need_sd_hotels):
            raise hotel_errors[0]
        scorer, risk_engine = ScoringEngine(ctx, self.scoring_config), RiskEngine(ctx)
        fastest = min((i.total_travel_minutes for i in itineraries), default=None)
        on_time = [i.cost.total for i in itineraries if i.cost.total is not None and i.arrival.buffer_minutes >= 0]
        cheapest_cost = min(on_time, default=None)
        for itin in itineraries:
            itin.scores = scorer.score(itin, fastest, cheapest_cost)
            itin.risk = risk_engine.assess(itin)
            itin.constraints = self._constraints(ctx, itin)
        self.funnel.itineraries_scored = len(itineraries)
        self.artifacts.itineraries = itineraries
        feasible = [i for i in itineraries if i.constraints and i.constraints.feasible]
        await self._emit("scoring", f"{len(itineraries)} journeys scored", itineraries=len(itineraries))

        # ---------------------------------------------------------- 7. reviews (top hotels only)
        await self._emit("reviews", "Comparing hotels")
        insights = await self._review_insights(ctx, feasible)
        for itin in itineraries:
            if itin.hotel and itin.hotel.id in insights:
                itin.risk = risk_engine.assess(itin, insights[itin.hotel.id])

        categories = self._categorise(feasible)
        for name, itin_id in categories.items():
            for itin in itineraries:
                if itin.id == itin_id:
                    itin.tags.append(name)

        # ---------------------------------------------------------- 8. local discovery
        await self._emit("places", f"Checking local options near {venue.name}")
        places = await places_task

        # ---------------------------------------------------------- 9. explanation
        summary = self._summary(ctx)
        by_id = {i.id: i for i in itineraries}
        explanation = None
        if categories.get("recommended"):
            await self._emit("explain", "Writing the recommendation")
            best = by_id[categories["recommended"]]
            alternatives = {k: by_id[v] for k, v in categories.items()}
            explanation = await explain_recommendation(self.settings, summary, best, alternatives, ai=self.ai_explainer,
                                                       tradeoff=self._tradeoff(by_id, categories, ctx))

        # ---------------------------------------------------------- assemble
        if not feasible:
            status = "no_options"
        elif any(i.constraints and i.constraints.all_ok for i in feasible):
            status = "complete"
        else:
            status = "partial"
        suggestions = self._suggestions(ctx, itineraries, feasible, relaxed_stop_ok, relaxed_rating,
                                        bool(all_flights or transit_all or ground_route), status, earliest_arrival)
        shown = self._select_for_display(itineraries, feasible, categories)

        return MissionResult(
            mission_id=mission_id,
            status=status,
            mode=self.provider.mode,
            mission=summary,
            categories=categories,
            itineraries=shown,
            modes=self._mode_summaries(ctx, modes | set(plan.modes_requested), itineraries, feasible, transit_all,
                                       ground_route, flight_error),
            tradeoff=self._tradeoff(by_id, categories, ctx),
            deltas=self._deltas(shown, by_id, categories),
            suggestions=suggestions,
            review_insights={k: v for k, v in insights.items() if any(i.hotel and i.hotel.id == k for i in shown)},
            places=places,
            explanation=explanation,
            funnel=self.funnel,
            data_sources=DataSources(mode=self.provider.mode, calls=self.tracker.calls,
                                     live_calls=self.tracker.live_calls, cache_hits=self.tracker.cache_hits,
                                     fetched_at=datetime.now(timezone.utc)),
            warnings=[*self.warnings, *(DEGRADED_MESSAGES[k] for k in self.degraded)],
            headline=self._headline(ctx, status, by_id.get(categories.get("recommended", ""))),
            route=plan,
            methodology=self._methodology(ctx, modes, bool(self.artifacts.hotels), bool(places)),
            diagnostics={"notes": self.debug_notes, "degraded": self.degraded},
        )

    # =================================================================== route intelligence helpers
    @staticmethod
    def _record_hubs(plan: RoutePlan, options: list[NormalizedTransit]) -> None:
        """Railway stations and bus points discovered in live transit results (first boarding / last alighting)."""
        stations: list[str] = []
        stops: list[str] = []
        for option in options:
            for seg in option.segments:
                if seg.mode == "train":
                    stations += [x for x in (seg.from_stop, seg.to_stop) if x]
                elif seg.mode == "bus" and seg.duration_minutes >= 35:
                    stops += [x for x in (seg.from_stop, seg.to_stop) if x]
        plan.railway_stations = list(dict.fromkeys(stations))[:6]
        plan.bus_points = list(dict.fromkeys(stops))[:6]

    def _methodology(self, ctx: MissionContext, modes: set[str], hotels: bool, places: bool) -> list[MethodNote]:
        if self.provider.mode == "demo":
            return [
                MethodNote(key="demo", label="Demo data", kind="demo",
                           detail="Schedules, prices, hotels and places come from a labelled demo dataset. "
                                  "No live searches are made."),
                MethodNote(key="calculated", label="Calculated", kind="calculated",
                           detail="Total trip cost, arrival buffer, risk and Mission Score — the same engine as live mode."),
            ]
        live = []
        if "flight" in modes and ctx.origin_airport is not None:
            live.append("flights (Google Flights)")
        if hotels:
            live.append("hotels (Google Hotels)")
        if modes & {"train", "bus"}:
            live.append("train and bus schedules (Google Maps transit)")
            if self.funnel.fares_matched:
                live.append("train and bus fares where Google Search shows them")
        live.append("routes (Google Maps)")
        if places:
            live.append("local places and reviews (Google Maps)")
        return [
            MethodNote(key="live", label="Live travel data", kind="live",
                       detail="Live " + ", ".join(live) + " — retrieved through SerpApi."),
            MethodNote(key="calculated", label="Calculated", kind="calculated",
                       detail="Door-to-door time, total trip cost, budget remaining, arrival buffer, risk and "
                              "Mission Score — by TripMission's deterministic scoring engine."),
            MethodNote(key="estimated", label="Estimated", kind="estimated",
                       detail="Taxi and cab fares, train and bus fares, airport check-in time and food — where "
                              "exact prices aren't available. Each is labelled where it appears."),
        ]


    # =================================================================== multi-modal
    MODE_LABEL = {"flight": "Flight", "train": "Train", "bus": "Bus", "transit": "Public transport", "ground": "Road trip"}

    @staticmethod
    def _mode_words(modes: set[str]) -> str:
        words = [w for m, w in (("flight", "flights"), ("train", "trains"), ("bus", "buses"), ("ground", "road routes"))
                 if m in modes]
        if not words:
            return "routes"
        return ", ".join(words[:-1]) + (" and " if len(words) > 1 else "") + words[-1]

    async def _search_transit(self, ctx: MissionContext, modes: set[str]) -> list[NormalizedTransit]:
        """Google Maps transit (SerpApi google_maps_directions, travel_mode=3) from the origin city to the venue,
        arriving with the required buffer. One search per requested vehicle (`prefer=train` / `prefer=bus`) so
        intercity buses aren't crowded out by trains; results are merged and de-duplicated."""
        req = ctx.request
        arrive_by = ctx.deadline - timedelta(minutes=req.min_buffer_minutes)
        wheelchair = bool({AccessibilityNeed.wheelchair, AccessibilityNeed.accessible_transport} & set(req.accessibility))
        prefers = [p for p in ("train", "bus") if p in modes]
        # Fares Google Search shows for these routes run alongside the schedule searches (optional, short timeout)
        fares_task = asyncio.gather(*[self._reported_fares(ctx, p) for p in prefers])
        results = await asyncio.gather(*[
            self.provider.transit_routes(
                f"{ctx.origin.city}", ctx.venue.location, end_label=ctx.venue.name, arrive_by=arrive_by,
                utc_offset_minutes=330 if ctx.destination.country == "IN" else 0, wheelchair=wheelchair,
                currency=ctx.currency, tracker=self.tracker, prefer=p)
            for p in prefers], return_exceptions=True)
        reported = [r for group in await fares_task for r in group]
        merged: dict[str, NormalizedTransit] = {}
        failures = 0
        for res in results:
            if isinstance(res, BaseException):
                if not isinstance(res, SerpApiError):
                    raise res
                failures += 1
                self.debug_notes.append(f"transit: {res.code}")
                continue
            for option in res:
                merged.setdefault(option.id, option)
        if failures and failures == len(results):
            self._degrade("transit")
        options = list(merged.values())
        self.funnel.fares_matched = attach_reported_fares(options, reported, ctx.currency)
        return options

    async def _reported_fares(self, ctx: MissionContext, mode: str) -> list[ReportedTransportRoute]:
        """Google Search transport-options fares for one mode. Optional enrichment: a failure, timeout or a
        provider without the lookup simply leaves fares estimated (and labelled so) — no user-facing warning."""
        lookup = getattr(self.provider, "transport_options", None)
        if lookup is None:
            return []
        try:
            return await asyncio.wait_for(
                lookup(mode, ctx.origin.city, ctx.destination.city, ctx.mission_date, tracker=self.tracker),
                timeout=self.settings.optional_timeout_seconds)
        except (asyncio.TimeoutError, SerpApiError) as exc:
            self.debug_notes.append(f"{mode} fares: {getattr(exc, 'code', 'timeout')}")
            return []

    async def _search_ground(self, ctx: MissionContext) -> NormalizedRoute | None:
        try:
            return await self.provider.directions(ctx.origin.city, ctx.venue.location,
                                                  start_label=ctx.origin.city, end_label=ctx.venue.name,
                                                  tracker=self.tracker, purpose="road trip (driving)")
        except SerpApiError as exc:
            self._degrade("road", exc.code)
            return None

    def _classify_transit(self, builder: ItineraryEngine, options: list[NormalizedTransit],
                          modes: set[str]) -> tuple[list[NormalizedTransit], list[NormalizedTransit]]:
        allowed = ({"train"} & modes) | ({"bus"} & modes)
        if allowed:
            allowed |= {"transit"}
        sd: list[NormalizedTransit] = []
        nb: list[NormalizedTransit] = []
        for option in options:
            if option.mode not in allowed:
                continue
            strategy = builder.strategy_for_arrival(option.arrival_time)
            if strategy is None or option.arrival_time > builder.ctx.deadline:
                continue
            if strategy == "night_before" and not builder.ctx.request.allow_previous_day:
                continue  # the traveller asked for same-day travel only
            (sd if strategy == "same_day" else nb).append(option)

        def shortlist(items: list[NormalizedTransit]) -> list[NormalizedTransit]:
            picks: list[NormalizedTransit] = []
            for mode in ("train", "bus", "transit"):
                ranked = sorted((o for o in items if o.mode == mode), key=lambda o: (o.duration_minutes, o.transfers))
                picks += ranked[:2]
            return picks

        return shortlist(sd), shortlist(nb)

    @staticmethod
    def _practical_ground(ctx: MissionContext, route: NormalizedRoute | None) -> NormalizedRoute | None:
        if route is None or route.duration_minutes > ctx.assumptions.max_practical_drive_minutes:
            return None
        return route

    def _build_transit_and_ground(self, builder, ctx, transit_sd, transit_nb, ground_route, sd_hotels, nb_hotels,
                                  routes) -> list[Itinerary]:
        req = ctx.request
        wheelchair = bool({AccessibilityNeed.wheelchair, AccessibilityNeed.accessible_transport} & set(req.accessibility))
        out: list[Itinerary] = []
        seen: set[str] = set()

        def add(itin: Itinerary | None) -> None:
            if itin and itin.id not in seen:
                seen.add(itin.id)
                out.append(itin)

        for option in transit_nb:
            for hotel in nb_hotels:
                add(builder.build_transit(option, hotel=hotel, hotel_to_venue=routes.get((hotel.id, "venue")),
                                          wheelchair_routed=wheelchair))
        for option in transit_sd:
            if req.hotel_required:
                for hotel in sd_hotels:
                    add(builder.build_transit(option, hotel=hotel, wheelchair_routed=wheelchair))
            else:
                add(builder.build_transit(option, hotel=None, wheelchair_routed=wheelchair))
        if ground_route is not None:
            if req.hotel_required:
                for hotel in sd_hotels[:2]:
                    add(builder.build_ground(ground_route, hotel=hotel))
            else:
                add(builder.build_ground(ground_route, hotel=None))
        return out

    def _mode_summaries(self, ctx, modes, itineraries, feasible, transit_all, ground_route, flight_error
                        ) -> list[ModeSummary]:
        out: list[ModeSummary] = []
        # Same ranking as the recommendation: journeys meeting every constraint first, then by score
        ranked = sorted(feasible, key=lambda i: (bool(i.constraints and i.constraints.all_ok),
                                                 i.scores.overall if i.scores else 0, -(i.risk.score if i.risk else 0)),
                        reverse=True)
        for mode in ("flight", "train", "bus", "ground"):
            if mode not in modes:
                continue
            group = [i for i in ranked if i.mode == mode or (mode == "bus" and i.mode == "transit")]
            if group:
                best = group[0]
                reason = {"flight": "Live prices from Google Flights",
                          "train": "Live schedule from Google Maps transit · estimated fare",
                          "bus": "Estimated bus/transit route from Google Maps · estimated fare",
                          "ground": "Live road route from Google Maps · estimated cab fare"}[mode]
                if mode in ("train", "bus") and best.transit and best.transit.fare_source == "google_search_transport_options":
                    reason = (f"Live schedule from Google Maps transit · fare shown by Google Search"
                              if mode == "train" else "Bus route from Google Maps transit · fare shown by Google Search")
                if self.provider.mode == "demo":
                    reason = "Demo dataset"
                if mode == "flight" and ctx.destination_airport and ctx.destination.code != ctx.destination_airport.code:
                    reason += f" · flight + road transfer via {ctx.destination_airport.code}"
                if mode == "flight" and best.practicality == "low":
                    reason += " · low practicality"
                out.append(ModeSummary(mode=best.mode, available=True, best_id=best.id, options=len(group),
                                       confidence=best.confidence, schedule_source=best.main.schedule_source,
                                       fare_source=best.cost.ticket_source, reason=reason))
                continue
            plan = ctx.plan
            if mode == "flight":
                reason = (plan.flight_reason if plan and plan.flight == "skipped" else
                          "Flight prices couldn't be loaded right now" if flight_error else
                          "No flight gets you there in time on these dates" if self.funnel.flights_found else
                          "No flights found between these airports")
            elif mode == "train":
                reason = ("Trains were found, but none arrive in time" if any(o.mode == "train" for o in transit_all)
                          else "Google Maps has no rail schedule for this route")
            elif mode == "bus":
                reason = ("Buses were found, but none arrive in time"
                          if any(o.mode in ("bus", "transit") for o in transit_all)
                          else "No intercity bus schedule in Google Maps for this route — check operators directly")
            elif plan and not plan.ground_search:
                reason = plan.ground_reason
            elif ground_route is None:
                reason = "No road route found"
            elif ground_route.duration_minutes > ctx.assumptions.max_practical_drive_minutes:
                reason = (f"{fmt_minutes(ground_route.duration_minutes)} by road "
                          f"({ground_route.distance_km:,.0f} km) — too long to be practical")
            else:
                reason = "The drive doesn't fit your constraints"
            out.append(ModeSummary(mode=mode, available=False, reason=reason))  # type: ignore[arg-type]
        return out

    @staticmethod
    def _tradeoff(by_id: dict[str, Itinerary], categories: dict[str, str], ctx: MissionContext) -> Tradeoff | None:
        cheap, fast = by_id.get(categories.get("cheapest", "")), by_id.get(categories.get("fastest", ""))
        if not cheap or not fast or cheap.id == fast.id or cheap.cost.total is None or fast.cost.total is None:
            return None
        extra = fast.cost.total - cheap.cost.total
        saved = cheap.total_travel_minutes - fast.total_travel_minutes
        if extra <= 0 or saved <= 0:
            return None
        hours = saved / 60
        time_text = (f"about {round(hours)} hour{'s' if round(hours) != 1 else ''}" if hours >= 1.5
                     else f"{saved} minutes")
        fast_word = MissionEngine.MODE_LABEL[fast.mode].lower()
        cheap_word = MissionEngine.MODE_LABEL[cheap.mode].lower()
        how = f" ({fast_word} instead of {cheap_word})" if fast.mode != cheap.mode else ""
        sentence = f"Spend {fmt_money(extra, ctx.currency)} more{how} to save {time_text} of travel."
        return Tradeoff(cheapest_id=cheap.id, fastest_id=fast.id, extra_cost=extra, time_saved_minutes=saved,
                        sentence=sentence)

    @staticmethod
    def _deltas(shown: list[Itinerary], by_id: dict[str, Itinerary], categories: dict[str, str]) -> dict[str, OptionDelta]:
        cheap, fast = by_id.get(categories.get("cheapest", "")), by_id.get(categories.get("fastest", ""))
        out: dict[str, OptionDelta] = {}
        for itin in shown:
            delta = OptionDelta()
            if fast and fast.cost.total is not None and itin.cost.total is not None:
                delta.money_saved_vs_fastest = round(fast.cost.total - itin.cost.total)
            if cheap:
                delta.time_saved_vs_cheapest_minutes = cheap.total_travel_minutes - itin.total_travel_minutes
            out[itin.id] = delta
        return out

    # =================================================================== stages
    async def _resolve_venue(self, request: MissionRequest, destination: ResolvedLocation) -> VenueInfo:
        """The venue is the mission's real endpoint; every final route ends there. Without one (or if it can't
        be found) the resolved destination's centre point is used — no extra "city centre" lookup needed."""
        if request.venue:
            try:
                place = await self.provider.geocode(f"{request.venue}, {destination.city}", tracker=self.tracker,
                                                    purpose="geocode venue")
            except SerpApiError as exc:
                self.debug_notes.append(f"venue geocode: {exc.code}")
                place = None
            if place and place.location and haversine_km(place.location, destination.location) <= 80:
                return VenueInfo(name=request.venue, address=place.address, location=place.location, resolved=True)
            self._warn(f'We couldn\'t pinpoint "{request.venue}" near {destination.city}, so distances are '
                       f'measured from the city centre.')
        return VenueInfo(name=f"{destination.city} city centre", address=None, location=destination.location,
                         resolved=False)

    async def _search_flights(self, ctx: MissionContext) -> tuple[list[NormalizedFlight], list[NormalizedFlight]]:
        req = ctx.request
        dates = [("mission day", ctx.mission_date)]
        if req.allow_previous_day:
            dates.append(("day before", ctx.day_before))
        # Search with up to 2 stops and filter locally, so "allow one connection" suggestions cost no extra calls.
        results = await asyncio.gather(*[
            self.provider.search_flights(ctx.origin_airport.code, ctx.destination_airport.code, d,
                                         adults=req.travelers, max_stops=2,
                                         currency=ctx.currency, tracker=self.tracker, purpose=f"flights ({label})")
            for label, d in dates], return_exceptions=True)
        out: list[list[NormalizedFlight]] = []
        errors: list[SerpApiError] = []
        for (label, d), res in zip(dates, results):
            if isinstance(res, BaseException):
                if not isinstance(res, SerpApiError):
                    raise res
                errors.append(res)
                self.debug_notes.append(f"flights ({label}): {res.code}")
                out.append([])
            else:
                out.append(res)
        if len(errors) == len(dates):
            raise errors[0]
        same_day = out[0]
        before = out[1] if len(out) > 1 else []
        return same_day, before

    def _estimate_minutes(self, a, b) -> int:
        return estimate_drive_minutes(haversine_km(a, b) * ROAD_FACTOR)

    def _classify_flights(self, ctx, builder, flights, est_airport_venue):
        req = ctx.request
        exit_min = ctx.assumptions.airport_exit_minutes
        optimistic = int(est_airport_venue * 0.8)
        sd, nb, relaxed = [], [], 0
        for f in flights:
            strategy = builder.strategy_for(f)
            if strategy is None:
                continue
            if strategy == "same_day":
                in_time = f.arrival_time + timedelta(minutes=exit_min + optimistic) <= ctx.deadline
            else:
                in_time = True
            if not in_time:
                continue
            if f.stops > req.max_stops:
                relaxed += 1
                continue
            (sd if strategy == "same_day" else nb).append(f)
        return sd, nb, relaxed

    @staticmethod
    def _earliest_venue_arrival(ctx, builder, flights, est_airport_venue) -> datetime | None:
        """Earliest realistic venue arrival on the mission day from any allowed flight (for suggestions)."""
        stop = ctx.assumptions.hotel_stop_minutes if ctx.request.hotel_required else 0
        times = [f.arrival_time + timedelta(minutes=ctx.assumptions.airport_exit_minutes + est_airport_venue + stop)
                 for f in flights if builder.strategy_for(f) == "same_day" and f.stops <= ctx.request.max_stops]
        return min(times, default=None)

    def _shortlist_same_day(self, ctx, flights, est_airport_venue) -> list[NormalizedFlight]:
        if not flights:
            return []
        n = self.settings.flight_shortlist_per_strategy
        r = ctx.required_buffer
        extra = ctx.assumptions.hotel_stop_minutes if ctx.request.hotel_required else 0
        priced = [f.price for f in flights if f.price]
        min_price = min(priced) if priced else None

        def est_buffer(f):
            arrive = f.arrival_time + timedelta(minutes=ctx.assumptions.airport_exit_minutes + est_airport_venue + extra)
            return (ctx.deadline - arrive).total_seconds() / 60

        def quick(f):
            bq = min(1.0, max(0.0, est_buffer(f)) / (r + 60))
            pq = (min_price / f.price) if (min_price and f.price) else 0.4
            stop_q = 1.0 if f.stops == 0 else 0.6
            return 0.5 * bq + 0.35 * pq + 0.15 * stop_q

        ranked = sorted(flights, key=quick, reverse=True)
        picks = ranked[:n]
        extras = [min(flights, key=lambda f: f.price if f.price else math.inf),
                  min(flights, key=lambda f: f.arrival_time),
                  min(flights, key=lambda f: f.duration_minutes)]
        for f in extras:
            if f not in picks and len(picks) < n + 2:
                picks.append(f)
        return picks

    def _shortlist_night_before(self, flights) -> list[NormalizedFlight]:
        if not flights:
            return []
        n = self.settings.flight_shortlist_per_strategy
        priced = [f.price for f in flights if f.price]
        min_price = min(priced) if priced else None

        def quick(f):
            pq = (min_price / f.price) if (min_price and f.price) else 0.4
            dep_q = 1.0 if f.departure_time.hour >= 6 else 0.5
            arr_q = 1.0 if f.arrival_time.hour < 22 else 0.3
            stop_q = 1.0 if f.stops == 0 else 0.6
            return 0.5 * pq + 0.15 * dep_q + 0.2 * arr_q + 0.15 * stop_q

        picks = sorted(flights, key=quick, reverse=True)[:n]
        cheapest = min(flights, key=lambda f: f.price if f.price else math.inf)
        if cheapest not in picks:
            picks.append(cheapest)
        return picks

    def _shortlist_hotels(self, ctx, hotels: list[NormalizedHotel]) -> tuple[list[NormalizedHotel], bool]:
        req = ctx.request
        for h in hotels:
            if h.location is not None:
                h.distance_km = round(haversine_km(h.location, ctx.venue.location), 1)
        # Search engines sometimes return properties in another city; a hotel far from the venue is never useful.
        hotels = [h for h in hotels if h.distance_km is None or h.distance_km <= self.settings.max_hotel_distance_km]
        usable = [h for h in hotels if h.price_per_night is not None or h.total_price is not None] or hotels
        qualifying = [h for h in usable if h.rating is not None and h.rating >= req.min_hotel_rating]
        relaxed = not qualifying and bool(usable)
        pool = qualifying or usable
        if not pool:
            return [], False
        prices = [h.total_price or h.price_per_night for h in pool if (h.total_price or h.price_per_night)]
        min_price = min(prices) if prices else None

        def pre(h: NormalizedHotel) -> float:
            loc = location_curve(h.distance_km)
            loc_q = (loc / 100) if loc is not None else 0.3
            rat_q = hotel_curve(h.rating, req.min_hotel_rating) / 100
            price = h.total_price or h.price_per_night
            price_q = (min_price / price) if (min_price and price) else 0.4
            return 0.45 * loc_q + 0.35 * rat_q + 0.2 * price_q

        ranked = sorted(pool, key=pre, reverse=True)
        picks = ranked[: self.settings.hotel_shortlist_per_stay]
        cheapest = min(pool, key=lambda h: (h.total_price or h.price_per_night or math.inf))
        if cheapest not in picks:
            picks.append(cheapest)
        for h in picks:
            self._hotel_prescore[h.id] = pre(h)
        return picks, relaxed

    async def _compute_routes(self, ctx: MissionContext, *, need_airport_venue: bool,
                              hotels: list[NormalizedHotel]) -> dict[tuple[str, str], NormalizedRoute]:
        airport, venue = ctx.destination_airport, ctx.venue
        airport_label = f"{airport.city} Airport ({airport.code})" if airport else ""
        jobs: list[tuple[tuple[str, str], Any, Any, str, str, bool]] = []
        if need_airport_venue and airport is not None:
            jobs.append((("airport", "venue"), airport.location, venue.location, airport_label, venue.name, True))

        unique: dict[str, NormalizedHotel] = {}
        for h in hotels:
            unique.setdefault(h.id, h)
        ordered = sorted(unique.values(), key=lambda h: self._hotel_prescore.get(h.id, 0), reverse=True)
        for idx, h in enumerate(ordered):
            if h.location is None:
                continue
            live = idx < self.settings.max_hotels_for_directions
            if airport is not None:  # airport → hotel only matters for flight journeys
                jobs.append((("airport", h.id), airport.location, h.location, airport_label, h.name, live))
            jobs.append(((h.id, "venue"), h.location, venue.location, h.name, venue.name, live))

        async def run(job):
            key, start, end, start_label, end_label, live = job
            if live:
                try:
                    route = await self.provider.directions(start, end, start_label=start_label, end_label=end_label,
                                                           tracker=self.tracker, purpose="directions")
                    if route is not None:
                        return key, route, True
                except SerpApiError as exc:
                    self._degrade("routes", exc.code)
            return key, estimate_route(start, end, start_label, end_label), False

        results = await asyncio.gather(*[run(j) for j in jobs])
        routes: dict[tuple[str, str], NormalizedRoute] = {}
        for key, route, live in results:
            routes[key] = route
            if live:
                self.funnel.routes_calculated += 1
        # Prefer road distance for "distance to venue" when we have it
        for h in hotels:
            route = routes.get((h.id, "venue"))
            if route is not None:
                h.distance_km = route.distance_km
        return routes

    def _build_all(self, builder, ctx, sd_short, nb_short, sd_hotels, nb_hotels, routes) -> list[Itinerary]:
        out: list[Itinerary] = []
        seen: set[str] = set()

        def add(itin: Itinerary | None):
            if itin and itin.id not in seen:
                seen.add(itin.id)
                out.append(itin)

        for f in sd_short:
            if ctx.request.hotel_required:
                for h in sd_hotels:
                    add(builder.build(f, hotel=h, airport_to_hotel=routes.get(("airport", h.id)),
                                      hotel_to_venue=routes.get((h.id, "venue"))))
            else:
                add(builder.build(f, hotel=None, airport_to_venue=routes.get(("airport", "venue"))))
        for f in nb_short:
            for h in nb_hotels:
                add(builder.build(f, hotel=h, airport_to_hotel=routes.get(("airport", h.id)),
                                  hotel_to_venue=routes.get((h.id, "venue"))))
        return out

    @staticmethod
    def _constraints(ctx: MissionContext, itin: Itinerary) -> ConstraintCheck:
        req = ctx.request
        feasible = itin.arrival.buffer_minutes >= 0
        within_budget = itin.cost.total is not None and itin.cost.total <= req.budget
        buffer_ok = itin.arrival.buffer_minutes >= req.min_buffer_minutes
        ground_ok = itin.ground_minutes_mission_day <= req.max_ground_minutes
        rating_ok = itin.hotel is None or (itin.hotel.rating is not None and itin.hotel.rating >= req.min_hotel_rating)
        return ConstraintCheck(feasible=feasible, within_budget=within_budget, buffer_ok=buffer_ok,
                               ground_ok=ground_ok, rating_ok=rating_ok,
                               all_ok=feasible and within_budget and buffer_ok and ground_ok and rating_ok)

    async def _review_insights(self, ctx: MissionContext, feasible: list[Itinerary]) -> dict[str, ReviewInsights]:
        ranked = sorted(feasible, key=lambda i: (i.scores.overall if i.scores else 0), reverse=True)
        hotels: dict[str, NormalizedHotel] = {}
        for itin in ranked:
            if itin.hotel is not None:
                hotels.setdefault(itin.hotel.id, itin.hotel)
        top_ids = list(hotels)[: self.settings.max_review_hotels]

        async def fetch(hotel: NormalizedHotel):
            bundle = await self._optional(self.provider.hotel_reviews(hotel.name, ctx.destination.city,
                                                                      near=hotel.location, tracker=self.tracker),
                                          "reviews")
            return hotel.id, bundle

        bundles = dict(await asyncio.gather(*[fetch(hotels[h]) for h in top_ids]))
        insights: dict[str, ReviewInsights] = {}
        for hotel_id, hotel in hotels.items():
            bundle = bundles.get(hotel_id)
            if bundle and bundle.reviews:
                self.artifacts.reviews[hotel_id] = bundle.reviews
            built = build_insights(hotel, bundle)
            if built:
                insights[hotel_id] = built
        return insights

    @staticmethod
    def _categorise(feasible: list[Itinerary]) -> dict[str, str]:
        if not feasible:
            return {}

        def cost(i: Itinerary) -> float:
            return i.cost.total if i.cost.total is not None else math.inf

        # A journey that satisfies every constraint always beats one that doesn't.
        pool = [i for i in feasible if i.constraints and i.constraints.all_ok] or feasible
        recommended = max(pool, key=lambda i: (i.scores.overall, -(i.risk.score), -cost(i)))
        cheapest = min(feasible, key=lambda i: (cost(i), -i.scores.overall))
        fastest = min(feasible, key=lambda i: (i.total_travel_minutes, i.door_to_venue_minutes, -i.scores.overall))
        safest = min(feasible, key=lambda i: (i.risk.score, -i.scores.arrival, -i.scores.overall))
        affordable = [i for i in feasible if i.constraints and i.constraints.within_budget] or feasible
        best_value = max(affordable, key=lambda i: (i.scores.value, i.scores.overall))
        return {"recommended": recommended.id, "cheapest": cheapest.id, "fastest": fastest.id, "safest": safest.id,
                "best_value": best_value.id}

    async def _places(self, ctx: MissionContext) -> list[PlaceGroup]:
        plan = PLACE_PLANS.get(str(ctx.request.mission_type), PLACE_PLANS["other"])[: self.settings.max_place_categories]
        near = f"{ctx.venue.name}, {ctx.destination.city}" if ctx.venue.resolved else ctx.destination.city

        async def fetch(slug, query, label, reason):
            items = await self._optional(self.provider.search_places(query, near, category=slug,
                                                                     city=ctx.destination.city, tracker=self.tracker),
                                         "places")
            if items is None:
                return None
            for item in items:
                if item.location is not None:
                    item.distance_km = round(haversine_km(item.location, ctx.venue.location), 1)
            items = [i for i in items if i.distance_km is None or i.distance_km <= 15]
            items.sort(key=lambda i: (i.distance_km if i.distance_km is not None else 99, -(i.rating or 0)))
            return PlaceGroup(category=slug, label=label, reason=reason, items=items[:6])

        groups = await asyncio.gather(*[fetch(*p) for p in plan])
        return [g for g in groups if g is not None]

    def _summary(self, ctx: MissionContext) -> MissionSummary:
        req = ctx.request
        return MissionSummary(
            origin=ctx.origin, destination=ctx.destination, origin_airport=ctx.origin_airport,
            destination_airport=ctx.destination_airport, venue=ctx.venue, mission_type=str(req.mission_type),
            travel_date=req.travel_date, arrival_deadline=req.arrival_deadline.strftime("%H:%M"),
            travelers=req.travelers, budget=req.budget, currency=req.currency,
            min_buffer_minutes=req.min_buffer_minutes, max_ground_minutes=req.max_ground_minutes,
            hotel_required=req.hotel_required, min_hotel_rating=req.min_hotel_rating, max_stops=req.max_stops,
            preferences=[str(p) for p in req.preferences], priority=str(req.priority),
            modes=[str(m) for m in req.modes], stay_nights=req.stay_nights, food_per_day=req.food_per_day,
            accessibility=[str(a) for a in req.accessibility])

    @staticmethod
    def _select_for_display(itineraries, feasible, categories) -> list[Itinerary]:
        if not feasible:
            return sorted(itineraries, key=lambda i: i.arrival.buffer_minutes, reverse=True)[:3]
        ranked = sorted(feasible, key=lambda i: i.scores.overall, reverse=True)
        chosen = set(categories.values())
        shown = [i for i in ranked if i.id in chosen]
        # Always show the best journey of each strategy so the same-day vs night-before trade-off is visible.
        for strategy in ("same_day", "night_before"):
            best = next((i for i in ranked if i.strategy == strategy), None)
            if best is not None and best not in shown:
                shown.append(best)
        for mode in ("flight", "train", "bus", "transit", "ground"):
            best = next((i for i in ranked if i.mode == mode), None)
            if best is not None and best not in shown:
                shown.append(best)
        # Fill with the next best, avoiding near-duplicates (same strategy + same hotel more than twice).
        seen: dict[tuple[str, str | None], int] = {}
        for itin in shown:
            key = (itin.strategy, itin.hotel.id if itin.hotel else None)
            seen[key] = seen.get(key, 0) + 1
        for itin in ranked:
            if len(shown) >= 10:
                break
            key = (itin.strategy, itin.hotel.id if itin.hotel else None)
            if itin in shown or seen.get(key, 0) >= 2:
                continue
            shown.append(itin)
            seen[key] = seen.get(key, 0) + 1
        return sorted(shown, key=lambda i: i.scores.overall, reverse=True)

    def _suggestions(self, ctx, itineraries, feasible, relaxed_stop_ok, relaxed_rating, any_flights,
                     status, earliest_arrival: datetime | None = None) -> list[Suggestion]:
        req = ctx.request
        out: list[Suggestion] = []
        cur = ctx.currency
        if status == "complete":
            return out
        if not any_flights:
            out.append(Suggestion(kind="no_flights", title="Try a different date",
                                  detail=f"No flights, trains or road routes were found between {ctx.origin.city} and "
                                         f"{ctx.destination.city} on these dates."))
            missing = [m for m in ("flight", "train", "bus", "ground") if m not in {str(x) for x in req.modes}]
            if missing:
                out.append(Suggestion(kind="more_modes", title="Consider every travel mode",
                                      detail="You limited the search to some modes.", unlocks="More options to compare",
                                      patch={"modes": ["flight", "train", "bus", "ground"]}))
            return out
        if not feasible:
            if not req.allow_previous_day:
                out.append(Suggestion(kind="previous_day", title="Travel the day before",
                                      detail="Nothing gets you there early enough on the day. Arriving the evening "
                                             "before is the most reliable fix.", unlocks="Night-before journeys",
                                      patch={"allow_previous_day": True,
                                             "preferences": [p for p in req.preferences if p != "same_day_only"]}))
            if relaxed_stop_ok and req.max_stops < 2:
                out.append(Suggestion(kind="allow_connection", title="Allow 1 connection",
                                      detail=f"{relaxed_stop_ok} connecting flight(s) would land in time.",
                                      unlocks="Additional flight options become available",
                                      patch={"max_stops": req.max_stops + 1}))
            latest = max(itineraries, key=lambda i: i.arrival.buffer_minutes, default=None)
            arrival = latest.arrival.venue_arrival if latest is not None else earliest_arrival
            if arrival is not None:
                start = arrival + timedelta(minutes=req.min_buffer_minutes)
                minutes = int(math.ceil((start.hour * 60 + start.minute) / 15.0) * 15)
                if start.date() == ctx.mission_date and minutes < 24 * 60:
                    label = f"{minutes // 60:02d}:{minutes % 60:02d}"
                    out.append(Suggestion(kind="later_deadline", title=f"A {label} start would work",
                                          detail=f"The earliest realistic arrival at the venue is around "
                                                 f"{fmt_clock(arrival)}, plus your {req.min_buffer_minutes}-minute buffer.",
                                          patch={"arrival_deadline": label}))
            return out

        # partial: something works, but not everything
        label = MissionEngine.MODE_LABEL
        others_ok = [i for i in feasible if i.constraints.buffer_ok and i.constraints.ground_ok and i.constraints.rating_ok]
        if others_ok and not any(i.constraints.within_budget for i in others_ok):
            priced = [i for i in others_ok if i.cost.total is not None]
            if priced:
                cheapest = min(priced, key=lambda i: i.cost.total)
                target = int(math.ceil(cheapest.cost.total / 100.0) * 100)
                out.append(Suggestion(
                    kind="increase_budget", title=f"Increase budget by {fmt_money(target - req.budget, cur)}",
                    detail=f"The cheapest journey that meets every other constraint costs "
                           f"{fmt_money(cheapest.cost.total, cur)}.",
                    unlocks=f"{label[cheapest.mode]} becomes available", patch={"budget": target}))
        affordable = [i for i in feasible if i.constraints.within_budget]
        if affordable and not any(i.constraints.buffer_ok for i in affordable):
            best = max(affordable, key=lambda i: i.arrival.buffer_minutes)
            relaxed_buffer = max(0, best.arrival.buffer_minutes // 5 * 5)
            out.append(Suggestion(kind="relax_buffer", title=f"Reduce arrival buffer to {relaxed_buffer} min",
                                  detail=f"Within budget, the best achievable buffer is {best.arrival.buffer_minutes} minutes.",
                                  unlocks=f"{label[best.mode]} becomes available",
                                  patch={"min_buffer_minutes": relaxed_buffer}))
        if relaxed_stop_ok and req.max_stops < 2:
            out.append(Suggestion(kind="allow_connection", title="Allow 1 connection",
                                  detail=f"{relaxed_stop_ok} more flight(s) would become possible.",
                                  unlocks="Additional flight options become available",
                                  patch={"max_stops": req.max_stops + 1}))
        if not any(i.constraints.ground_ok for i in feasible):
            best_ground = min(i.ground_minutes_mission_day for i in feasible)
            allowed = int(math.ceil(best_ground / 15.0) * 15)
            out.append(Suggestion(kind="ground_time", title=f"Allow {fmt_minutes(allowed)} of ground travel",
                                  detail=f"The shortest transfer on the day is {fmt_minutes(best_ground)}.",
                                  patch={"max_ground_minutes": allowed}))
        if relaxed_rating:
            ratings = [i.hotel.rating for i in feasible if i.hotel and i.hotel.rating]
            if ratings:
                best = max(ratings)
                out.append(Suggestion(kind="hotel_rating", title=f"Lower minimum hotel rating to {best:.1f}",
                                      detail="No hotel near the venue met your minimum rating.",
                                      patch={"min_hotel_rating": math.floor(best * 2) / 2}))
        hotels = [i.hotel for i in feasible if i.hotel and i.hotel.distance_km is not None]
        if hotels and min(h.distance_km for h in hotels) > 5:
            out.append(Suggestion(kind="hotel_radius", title="Expand the hotel search",
                                  detail="Every hotel found is more than 5 km from the venue. Try naming a nearby "
                                         "landmark as the venue.", patch={}))
        return out

    @staticmethod
    def _headline(ctx: MissionContext, status: str, best: Itinerary | None) -> str:
        noun = mission_noun(ctx.request.mission_type)
        deadline = ctx.request.arrival_deadline.strftime("%H:%M")
        if status == "no_options" or best is None:
            return f"No journey gets you to your {noun} by {deadline}."
        verb = {"flight": "Fly in", "train": "Take the train in", "bus": "Take the bus in",
                "transit": "Travel in", "ground": "Drive in"}[best.mode]
        overnight = best.strategy == "same_day" and best.main.departure_time.date() < ctx.mission_date
        if best.strategy == "night_before":
            when = f"{verb} the {'evening' if best.main.arrival_time.hour >= 17 else 'day'} before"
        elif overnight:
            when = {"flight": "Take the overnight flight", "train": "Take the overnight train",
                    "bus": "Take the overnight bus", "transit": "Travel overnight",
                    "ground": "Drive overnight"}[best.mode]
        else:
            when = {"flight": "Fly the same morning", "train": "Take the train on the day",
                    "bus": "Take the bus on the day", "transit": "Travel on the day",
                    "ground": "Drive there on the day"}[best.mode]
        tail = f"arrive with {best.arrival.buffer_minutes} minutes to spare."
        if status == "partial":
            return f"Closest match: {when.lower()} and {tail}"
        return f"{when} and {tail}"
