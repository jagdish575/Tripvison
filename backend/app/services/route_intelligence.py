"""RouteIntelligenceService — decides which travel modes make sense before any search is spent.

TripMission plans DOOR → DOOR, not airport → airport. For every mission it works out:
  * the straight-line and estimated road distance between the two places
  * which airport to fly from / to — the city's own, or the nearest *practical* one (road transfer
    within MAX_PRACTICAL_AIRPORT_TRANSFER_MINUTES of the venue)
  * whether flying is meaningful at all (short trips, shared airports and missing airports skip it)
  * whether a road search is worth a live request
and produces friendly routing notices. Missing airports are routing decisions, never errors.
Nothing here is city-specific: it runs on coordinates and configurable thresholds.
"""

from __future__ import annotations

from app.core.config import Settings
from app.schemas.result import RouteNotice, RoutePlan
from app.schemas.travel import GeoPoint, NearbyHub, ResolvedLocation
from app.services.airports import AIRPORTS
from app.services.geo import estimate_transfer_minutes, haversine_km, road_km_estimate
from app.services.location_resolution import airport_hub, nearby_airports
from app.utils.format import fmt_minutes

GROUND_SEARCH_SLACK = 1.15  # skip the live road search when the estimate is clearly beyond the practical limit
SURFACE_MODES = ("train", "bus", "ground")


def airport_label(hub: NearbyHub) -> str:
    return f"{hub.city} Airport ({hub.code})"


class RouteIntelligenceService:
    def __init__(self, settings: Settings, *, max_practical_drive_minutes: int = 16 * 60) -> None:
        self.settings = settings
        self.max_drive = max_practical_drive_minutes

    def plan(self, origin: ResolvedLocation, destination: ResolvedLocation, venue: GeoPoint,
             modes: list[str]) -> RoutePlan:
        s = self.settings
        distance = haversine_km(origin.location, destination.location)
        road_km = road_km_estimate(origin.location, destination.location)
        road_minutes = estimate_transfer_minutes(road_km)
        o_air = self._origin_airport(origin)
        d_air = self._destination_airport(destination, venue)
        plan = RoutePlan(distance_km=round(distance, 1), road_km=road_km, road_minutes=road_minutes,
                         origin_airport=o_air, destination_airport=d_air, origin_has_airport=origin.has_airport,
                         destination_has_airport=destination.has_airport, modes_requested=list(modes))
        notices: list[RouteNotice] = []
        evaluated = [m for m in modes if m != "flight"]

        # ------------------------------------------------------------ airport facts (always worth saying)
        if not destination.has_airport:
            if d_air is not None:
                notices.append(RouteNotice(kind="airport_fallback", message=(
                    f"{destination.city} doesn't have a commercial airport. The nearest practical airport is "
                    f"{airport_label(d_air)}, about {fmt_minutes(d_air.transfer_minutes or 0)} by road from your venue.")))
            else:
                notices.append(RouteNotice(kind="no_airport", message=(
                    f"{destination.city} doesn't have a commercial airport within a practical road transfer, "
                    f"so we focused on train, bus and road.")))

        # ------------------------------------------------------------ flight decision
        if "flight" in modes:
            reason = None
            if distance < s.min_flight_distance_km:
                reason = (f"{origin.city} → {destination.city} is only about {road_km:,.0f} km by road, so we compared "
                          f"train, bus and road instead of searching flights.")
                kind = "short_distance"
            elif o_air is None:
                reason = f"There's no practical airport near {origin.city}, so flights were skipped."
                kind = "flight_skipped"
            elif d_air is None:
                reason = f"There's no practical airport near {destination.city}, so flights were skipped."
                kind = "flight_skipped"
            elif o_air.code == d_air.code:
                reason = (f"{origin.city} and {destination.city} share the same nearest airport "
                          f"({o_air.code}), so flying doesn't help — we compared surface travel instead.")
                kind = "flight_skipped"
            if reason:
                plan.flight, plan.flight_reason = "skipped", reason
                notices.append(RouteNotice(kind=kind, message=reason))
            else:
                assert o_air is not None and d_air is not None
                plan.flight = "searched"
                evaluated.insert(0, "flight")
                worst = max(o_air.transfer_minutes or 0, d_air.transfer_minutes or 0)
                plan.flight_practicality = "low" if worst > s.low_practicality_airport_transfer_minutes else "high"
                if not destination.has_airport:
                    notices[0] = RouteNotice(kind="airport_fallback", message=(
                        f"{destination.city} doesn't have a commercial airport. We found {airport_label(d_air)} as the "
                        f"nearest practical airport and added the road transfer to your journey."))
                if not origin.has_airport:
                    notices.append(RouteNotice(kind="origin_transfer", message=(
                        f"{origin.city} doesn't have a commercial airport, so flight journeys start with a road "
                        f"transfer to {airport_label(o_air)}.")))
                if plan.flight_practicality == "low":
                    notices.append(RouteNotice(kind="low_practicality", message=(
                        f"Flying needs about {fmt_minutes(worst)} of airport road transfer, so flight options are "
                        f"marked low practicality.")))

        # ------------------------------------------------------------ road decision
        if "ground" in modes and road_minutes > self.max_drive * GROUND_SEARCH_SLACK:
            plan.ground_search = False
            plan.ground_reason = (f"About {fmt_minutes(road_minutes)} by road ({road_km:,.0f} km) — too long to be "
                                  f"practical")

        # ------------------------------------------------------------ never leave the traveller without options
        practical_surface = [m for m in evaluated if m != "ground" or plan.ground_search]
        if not practical_surface:
            added = [m for m in SURFACE_MODES if m not in evaluated and (m != "ground" or plan.ground_search)]
            if "ground" in evaluated and not plan.ground_search:
                added = [m for m in ("train", "bus") if m not in evaluated]
            if added:
                evaluated += added
                words = {"train": "train", "bus": "bus", "ground": "road"}
                notices.append(RouteNotice(kind="modes_added", message=(
                    "None of the travel modes you picked work for this trip, so we also compared "
                    + " and ".join(words[m] for m in added) + ".")))
        plan.modes_evaluated = [m for m in ("flight", "train", "bus", "ground") if m in evaluated]
        plan.notices = notices
        return plan

    # ------------------------------------------------------------------ hubs
    def _origin_airport(self, origin: ResolvedLocation) -> NearbyHub | None:
        if origin.code and origin.code in AIRPORTS:
            return airport_hub(AIRPORTS[origin.code], origin.location, self.settings.max_practical_airport_transfer_minutes)
        practical = [h for h in origin.nearby_airports if h.practical]
        return min(practical, key=lambda h: h.transfer_minutes or 0, default=None)

    def _destination_airport(self, destination: ResolvedLocation, venue: GeoPoint) -> NearbyHub | None:
        limit = self.settings.max_practical_airport_transfer_minutes
        if destination.code and destination.code in AIRPORTS:
            return airport_hub(AIRPORTS[destination.code], venue, limit)
        practical = [h for h in nearby_airports(venue, limit) if h.practical]
        return min(practical, key=lambda h: h.transfer_minutes or 0, default=None)
