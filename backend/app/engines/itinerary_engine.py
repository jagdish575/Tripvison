"""Builds complete, timed journeys for every travel mode from normalized parts.

Flight:   home → origin airport (+ check-in) → flight → airport → (hotel) → venue — door to door
Train/Bus/Transit: Google Maps transit option (+ hotel) — schedule LIVE, fare usually ESTIMATED
Ground:   one long drive to the venue                     — route LIVE, cab fare ESTIMATED

Every cost line carries its source: live | estimated | user_provided | calculated.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from app.engines.context import MissionContext
from app.schemas.mission import DEFAULT_FOOD_PER_DAY, AccessibilityNeed
from app.schemas.result import (AccessibilityNote, ArrivalInfo, CostBreakdown, CostItem, GroundLeg, Itinerary,
                                MainLeg, Strategy, TimelineEvent)
from app.schemas.travel import Airport, NormalizedFlight, NormalizedHotel, NormalizedRoute, NormalizedTransit
from app.services.geo import estimate_route
from app.utils.format import fmt_minutes, fmt_money, mission_noun

MODE_WORD = {"train": "Train", "bus": "Bus", "metro": "Metro / city bus", "ferry": "Ferry", "other": "Transit",
             "walk": "Walk"}


class ItineraryEngine:
    def __init__(self, ctx: MissionContext) -> None:
        self.ctx = ctx
        self.a = ctx.assumptions

    # ------------------------------------------------------------------ helpers
    def strategy_for_arrival(self, arrival: datetime) -> Strategy | None:
        landed = arrival.date()
        if landed == self.ctx.mission_date:
            return "same_day"
        if landed < self.ctx.mission_date:
            return "night_before"
        return None

    def strategy_for(self, flight: NormalizedFlight) -> Strategy | None:
        """Flights: only the mission day and the day before are searched/considered."""
        landed = flight.arrival_time.date()
        if landed == self.ctx.mission_date:
            return "same_day"
        if landed == self.ctx.day_before:
            return "night_before"
        return None

    def taxi_fare(self, km: float) -> float:
        cabs = math.ceil(self.ctx.request.travelers / 4)
        return round((self.a.taxi_base_fare + self.a.taxi_per_km * km) * cabs)

    def _leg(self, route: NormalizedRoute, start: datetime, from_kind: str, to_kind: str, day: str,
             *, from_label: str | None = None, to_label: str | None = None) -> GroundLeg:
        return GroundLeg(
            from_label=from_label or route.origin_label, to_label=to_label or route.destination_label,
            from_kind=from_kind, to_kind=to_kind,  # type: ignore[arg-type]
            depart_at=start, arrive_at=start + timedelta(minutes=route.duration_minutes),
            duration_minutes=route.duration_minutes, typical_max_minutes=route.typical_max_minutes,
            distance_km=route.distance_km, mode="Taxi", estimated=route.estimated,
            cost=self.taxi_fare(route.distance_km), day=day,  # type: ignore[arg-type]
        )

    @staticmethod
    def _flight_mode(flight: NormalizedFlight) -> str:
        if flight.stops == 0:
            return "Direct flight"
        via = ", ".join(l.airport for l in flight.layovers if l.airport)
        label = f"Flight · {flight.stops} stop{'s' if flight.stops > 1 else ''}"
        return f"{label} via {via}" if via else label

    # ------------------------------------------------------------------ shared pieces
    def _hotel_stay(self, strategy: Strategy, arrival: datetime, hotel: NormalizedHotel | None
                    ) -> tuple[date | None, date | None, int, float | None, str]:
        """Returns check-in, check-out, nights, cost and cost source for the hotel part of a journey."""
        if hotel is None:
            return None, None, 0, None, "live"
        nights = self.ctx.request.stay_nights
        if strategy == "night_before":
            check_in = min(arrival.date(), self.ctx.day_before)
            extra = (self.ctx.day_before - check_in).days  # e.g. a train that arrives two days early
            nights += extra
        else:
            check_in, extra = self.ctx.mission_date, 0
        check_out = check_in + timedelta(days=nights)
        if hotel.total_price is not None and extra == 0:
            return check_in, check_out, nights, hotel.total_price, "live"
        if hotel.price_per_night is not None:
            return check_in, check_out, nights, hotel.price_per_night * nights, "calculated" if extra else "live"
        return check_in, check_out, nights, None, "live"

    def _food(self, departure: datetime) -> tuple[float, int, str]:
        req = self.ctx.request
        days = max(1, (self.ctx.mission_date - departure.date()).days + 1)
        amount = round(req.food_per_day * days * req.travelers)
        source = "user_provided" if req.food_per_day != DEFAULT_FOOD_PER_DAY else "estimated"
        return amount, days, source

    def _costs(self, *, ticket: float | None, ticket_source: str, ticket_label: str, ticket_detail: str | None,
               legs: list[GroundLeg], extra_ground: float = 0.0, extra_ground_detail: str | None = None,
               hotel: NormalizedHotel | None, hotel_cost: float | None, hotel_source: str, nights: int,
               departure: datetime) -> CostBreakdown:
        req, cur = self.ctx.request, self.ctx.currency
        items: list[CostItem] = []
        if ticket is not None:
            items.append(CostItem(key="ticket", label=ticket_label, amount=round(ticket), source=ticket_source,  # type: ignore[arg-type]
                                  detail=ticket_detail))
        ground = round(sum(l.cost for l in legs) + extra_ground)
        if ground:
            parts = [f"{len(legs)} taxi ride{'s' if len(legs) != 1 else ''} at ₹100 + ₹18/km"] if legs else []
            if extra_ground_detail:
                parts.append(extra_ground_detail)
            items.append(CostItem(key="ground", label="Ground transport", amount=ground, source="estimated",
                                  detail=" + ".join(parts) or None))
        if hotel is not None and hotel_cost is not None:
            per_night = hotel.price_per_night or (hotel_cost / nights if nights else None)
            items.append(CostItem(key="hotel", label=f"Hotel · {nights} night{'s' if nights != 1 else ''}",
                                  amount=round(hotel_cost), source=hotel_source,  # type: ignore[arg-type]
                                  detail=f"{fmt_money(per_night, cur)}/night × {nights}" if per_night else None))
        food, days, food_source = self._food(departure)
        if food:
            items.append(CostItem(key="food", label="Food", amount=food, source=food_source,  # type: ignore[arg-type]
                                  detail=f"{fmt_money(req.food_per_day, cur)}/day × {days} day{'s' if days != 1 else ''}"
                                         + (f" × {req.travelers} people" if req.travelers > 1 else "")))
        known = ticket is not None and (hotel is None or hotel_cost is not None)
        total = round(sum(i.amount for i in items)) if known else None
        return CostBreakdown(
            ticket=round(ticket) if ticket is not None else None, hotel=round(hotel_cost) if hotel_cost else None,
            ground=ground, food=food, total=total, currency=cur, ground_estimated=True, hotel_nights=nights,
            hotel_per_night=hotel.price_per_night if hotel else None, ticket_price_known=ticket is not None,
            ticket_source=ticket_source, items=items, budget=req.budget,  # type: ignore[arg-type]
            budget_remaining=round(req.budget - total) if total is not None else None)

    def _accessibility(self, mode: str, hotel: NormalizedHotel | None, wheelchair_routed: bool) -> list[AccessibilityNote]:
        needs = set(self.ctx.request.accessibility)
        if not needs:
            return []
        notes: list[AccessibilityNote] = []
        amenities = " · ".join(hotel.amenities).lower() if hotel else ""
        if needs & {AccessibilityNeed.wheelchair, AccessibilityNeed.accessible_transport}:
            if mode == "flight":
                notes.append(AccessibilityNote(need="Accessible transport", status="unavailable",
                    detail="Airlines provide wheelchair assistance on request — book it with the airline. "
                           "Our data doesn't confirm it."))
            elif mode in ("train", "bus", "transit"):
                notes.append(AccessibilityNote(
                    need="Accessible transport", status="requested" if wheelchair_routed else "unavailable",
                    detail="Google Maps was asked for its wheelchair-accessible transit routing; station access "
                           "isn't confirmed." if wheelchair_routed else "Accessibility information unavailable."))
            else:
                notes.append(AccessibilityNote(need="Accessible transport", status="unavailable",
                                               detail="Accessibility information unavailable for cabs."))
        if needs & {AccessibilityNeed.accessible_hotel, AccessibilityNeed.wheelchair} and hotel is not None:
            match = next((a for a in hotel.amenities if "accessib" in a.lower() or "wheelchair" in a.lower()), None)
            notes.append(AccessibilityNote(
                need="Accessible hotel", status="available" if match else "unavailable",
                detail=f"Hotel lists “{match}”." if match else "Accessibility information unavailable."))
        if AccessibilityNeed.elevator in needs and hotel is not None:
            has_lift = "elevator" in amenities or "lift" in amenities
            notes.append(AccessibilityNote(need="Elevator", status="available" if has_lift else "unavailable",
                                           detail="Hotel lists an elevator." if has_lift
                                           else "Accessibility information unavailable."))
        return notes

    def _finish(self, *, ident: str, mode: str, strategy: Strategy, main: MainLeg, legs: list[GroundLeg],
                timeline: list[TimelineEvent], venue_arrival: datetime, departure: datetime, cost: CostBreakdown,
                hotel: NormalizedHotel | None, check_in: date | None, check_out: date | None,
                leave_hotel_at: datetime | None, total_travel: int, extra_mission_ground: int = 0,
                extra_before_ground: int = 0, quality: list[str], confidence: str,
                flight: NormalizedFlight | None = None, transit: NormalizedTransit | None = None,
                wheelchair_routed: bool = False) -> Itinerary:
        deadline = self.ctx.deadline
        buffer = int(round((deadline - venue_arrival).total_seconds() / 60))
        noun = mission_noun(self.ctx.request.mission_type)
        timeline.append(TimelineEvent(
            time=venue_arrival, kind="arrive", title=f"Arrive at {self.ctx.venue.name}",
            detail=f"{fmt_minutes(abs(buffer))} {'before' if buffer >= 0 else 'after'} your {noun} starts",
            duration_to_next_minutes=max(buffer, 0), mode_to_next="Buffer"))
        timeline.append(TimelineEvent(time=deadline, kind="deadline", title=f"{noun.capitalize()} begins",
                                      detail="Required arrival"))
        return Itinerary(
            id=ident, mode=mode, strategy=strategy, main=main, flight=flight, transit=transit, hotel=hotel,  # type: ignore[arg-type]
            hotel_check_in=check_in, hotel_check_out=check_out, legs=legs, timeline=timeline, cost=cost,
            arrival=ArrivalInfo(venue_arrival=venue_arrival, deadline=deadline, buffer_minutes=buffer,
                                required_buffer_minutes=self.ctx.required_buffer, leave_hotel_at=leave_hotel_at,
                                effective_buffer_minutes=buffer),
            # Ground-time constraints are about the destination side; the home → airport ride is part of
            # the door-to-door time and cost but not of "ground travel on the day" at the destination.
            ground_minutes_mission_day=sum(l.duration_minutes for l in legs if l.day == "mission" and l.from_kind != "origin")
            + extra_mission_ground,
            ground_minutes_before=sum(l.duration_minutes for l in legs if l.day == "before" and l.from_kind != "origin")
            + extra_before_ground,
            total_travel_minutes=total_travel,
            door_to_venue_minutes=int((venue_arrival - departure).total_seconds() // 60),
            confidence=confidence,  # type: ignore[arg-type]
            data_quality=quality,
            accessibility=self._accessibility(mode, hotel, wheelchair_routed),
        )

    def _hotel_key(self, hotel: NormalizedHotel | None) -> str:
        return hotel.id.removeprefix("h-")[:10] if hotel else "nohotel"

    def _airports(self, flight: NormalizedFlight) -> tuple[Airport, Airport]:
        from app.services.airports import AIRPORTS

        ctx = self.ctx
        dep = ctx.origin_airport or AIRPORTS.get(flight.departure_airport)
        arr = ctx.destination_airport or AIRPORTS.get(flight.arrival_airport)
        if dep is None or arr is None:
            raise ValueError("flight journeys need resolved airports")
        return dep, arr

    def _access_leg(self, airport: Airport, flight: NormalizedFlight, day: str) -> GroundLeg:
        """Home (origin city) → departure airport, timed to arrive `airport_checkin_minutes` before take-off.
        Always an estimate: it is never searched live, to keep the search budget for the destination side."""
        ctx = self.ctx
        route = estimate_route(ctx.origin.location, airport.location, ctx.origin.city, f"{airport.city} Airport")
        arrive = flight.departure_time - timedelta(minutes=self.a.airport_checkin_minutes)
        return self._leg(route, arrive - timedelta(minutes=route.duration_minutes), "origin", "airport", day)

    # ------------------------------------------------------------------ flight
    def build(self, flight: NormalizedFlight, *, hotel: NormalizedHotel | None,
              airport_to_venue: NormalizedRoute | None = None, airport_to_hotel: NormalizedRoute | None = None,
              hotel_to_venue: NormalizedRoute | None = None) -> Itinerary | None:
        strategy = self.strategy_for(flight)
        if strategy is None:
            return None
        ctx, a = self.ctx, self.a
        dep_airport, dest = self._airports(flight)
        deadline = ctx.deadline
        legs: list[GroundLeg] = []
        timeline: list[TimelineEvent] = []
        leave_hotel_at: datetime | None = None
        exit_at = flight.arrival_time + timedelta(minutes=a.airport_exit_minutes)
        access = self._access_leg(dep_airport, flight, "before" if strategy == "night_before" else "mission")
        far_from_home = ctx.origin.code != dep_airport.code

        timeline.append(TimelineEvent(
            time=access.depart_at, kind="depart", title=f"Leave {ctx.origin.city} for the airport",
            detail=(f"Road transfer to {dep_airport.city} Airport ({dep_airport.code})" if far_from_home
                    else dep_airport.name) + " · time estimated",
            duration_to_next_minutes=access.duration_minutes, mode_to_next="Taxi", distance_to_next_km=access.distance_km))
        timeline.append(TimelineEvent(
            time=access.arrive_at, kind="transfer", title=f"Check in at {dep_airport.code}",
            detail=f"Arrive {a.airport_checkin_minutes} minutes before departure",
            duration_to_next_minutes=a.airport_checkin_minutes, mode_to_next="Check-in & security"))
        timeline.append(TimelineEvent(
            time=flight.departure_time, kind="board", title=f"Take off from {dep_airport.city} ({flight.departure_airport})",
            detail=f"{flight.airline} · {', '.join(flight.flight_numbers)}",
            duration_to_next_minutes=flight.duration_minutes, mode_to_next=self._flight_mode(flight)))
        timeline.append(TimelineEvent(
            time=flight.arrival_time, kind="land", title=f"Land at {dest.city} ({flight.arrival_airport})",
            detail=dest.name if ctx.destination.code == dest.code else
            f"{dest.name} — nearest practical airport to {ctx.destination.city}",
            duration_to_next_minutes=a.airport_exit_minutes, mode_to_next="Deplane & exit"))

        if strategy == "same_day":
            if hotel is not None:
                if airport_to_hotel is None or hotel_to_venue is None:
                    return None
                leg1 = self._leg(airport_to_hotel, exit_at, "airport", "hotel", "mission")
                stop_end = leg1.arrive_at + timedelta(minutes=a.hotel_stop_minutes)
                leg2 = self._leg(hotel_to_venue, stop_end, "hotel", "venue", "mission")
                legs = [leg1, leg2]
                venue_arrival = leg2.arrive_at
                timeline += [
                    TimelineEvent(time=exit_at, kind="exit", title="Leave the airport", detail="Pre-book a cab to skip the queue",
                                  duration_to_next_minutes=leg1.duration_minutes, mode_to_next="Taxi",
                                  distance_to_next_km=leg1.distance_km),
                    TimelineEvent(time=leg1.arrive_at, kind="hotel", title=f"Drop bags at {hotel.name}",
                                  detail=f"{a.hotel_stop_minutes}-minute stop · room for tonight",
                                  duration_to_next_minutes=a.hotel_stop_minutes, mode_to_next="Freshen up"),
                    TimelineEvent(time=stop_end, kind="leave", title="Leave the hotel",
                                  duration_to_next_minutes=leg2.duration_minutes, mode_to_next="Taxi",
                                  distance_to_next_km=leg2.distance_km)]
            else:
                if airport_to_venue is None:
                    return None
                leg = self._leg(airport_to_venue, exit_at, "airport", "venue", "mission")
                legs = [leg]
                venue_arrival = leg.arrive_at
                timeline.append(TimelineEvent(
                    time=exit_at, kind="exit", title="Leave the airport", detail="Head straight to the venue",
                    duration_to_next_minutes=leg.duration_minutes, mode_to_next="Taxi", distance_to_next_km=leg.distance_km))
        else:
            if hotel is None or airport_to_hotel is None or hotel_to_venue is None:
                return None
            leg1 = self._leg(airport_to_hotel, exit_at, "airport", "hotel", "before")
            planned_buffer = ctx.required_buffer + a.night_before_extra_margin_minutes
            venue_arrival = deadline - timedelta(minutes=planned_buffer)
            leave_hotel_at = venue_arrival - timedelta(minutes=hotel_to_venue.duration_minutes)
            leg2 = self._leg(hotel_to_venue, leave_hotel_at, "hotel", "venue", "mission")
            legs = [leg1, leg2]
            timeline += [
                TimelineEvent(time=exit_at, kind="exit", title="Leave the airport",
                              duration_to_next_minutes=leg1.duration_minutes, mode_to_next="Taxi",
                              distance_to_next_km=leg1.distance_km),
                TimelineEvent(time=leg1.arrive_at, kind="hotel", title=f"Check in at {hotel.name}",
                              detail="Overnight stay — rest before the big day", mode_to_next="Overnight"),
                TimelineEvent(time=leave_hotel_at, kind="leave", title="Leave the hotel",
                              detail=f"Planned for a {planned_buffer}-minute buffer",
                              duration_to_next_minutes=leg2.duration_minutes, mode_to_next="Taxi",
                              distance_to_next_km=leg2.distance_km)]

        legs = [access, *legs]
        check_in, check_out, nights, hotel_cost, hotel_source = self._hotel_stay(strategy, flight.arrival_time, hotel)
        demo = flight.source == "demo"
        cost = self._costs(
            ticket=flight.price, ticket_source="live", ticket_label="Flight",
            ticket_detail=f"{flight.airline} {', '.join(flight.flight_numbers)} · {'Demo dataset' if demo else 'Google Flights'}"
                          + (f" · {ctx.request.travelers} travellers" if ctx.request.travelers > 1 else ""),
            legs=legs, hotel=hotel, hotel_cost=hotel_cost, hotel_source=hotel_source, nights=nights,
            departure=access.depart_at)
        stop = a.hotel_stop_minutes if (strategy == "same_day" and hotel is not None) else 0
        total_travel = (a.airport_checkin_minutes + flight.duration_minutes + a.airport_exit_minutes
                        + sum(l.duration_minutes for l in legs) + stop)

        quality = [f"{l.from_label} → {l.to_label} time estimated from distance" for l in legs
                   if l.estimated and l.from_kind != "origin"]
        quality.append(f"Ride to {dep_airport.code} and {a.airport_checkin_minutes}-minute check-in are estimates")
        if flight.price is None:
            quality.append("Flight price not available")
        if hotel is not None and hotel_cost is None:
            quality.append("Hotel price not available")
        if hotel is not None and hotel.location is None:
            quality.append("Hotel location not available")

        main = MainLeg(
            mode="flight", provider=flight.airline, title=f"{flight.airline} {' / '.join(flight.flight_numbers)}",
            references=flight.flight_numbers, departure_label=f"{dep_airport.city} ({flight.departure_airport})",
            arrival_label=f"{dest.city} ({flight.arrival_airport})", departure_time=flight.departure_time,
            arrival_time=flight.arrival_time, duration_minutes=flight.duration_minutes, stops=flight.stops,
            transfers=flight.stops, schedule_source="live", data_source="Demo dataset" if demo else "Google Flights",
            note=None if ctx.destination.code == dest.code else
            f"Flight + ground transfer: {ctx.destination.city} has no commercial airport, so you land at {dest.city} "
            f"({dest.code}) and continue by road.")
        ident = f"{'nb' if strategy == 'night_before' else 'sd'}-{flight.flight_numbers[0].replace(' ', '')}-{self._hotel_key(hotel)}"
        itin = self._finish(
            ident=ident, mode="flight", strategy=strategy, main=main, legs=legs, timeline=timeline,
            venue_arrival=venue_arrival, departure=access.depart_at, cost=cost, hotel=hotel, check_in=check_in,
            check_out=check_out, leave_hotel_at=leave_hotel_at, total_travel=total_travel, quality=quality,
            confidence="high" if len(quality) <= 1 else "medium", flight=flight)
        if ctx.plan is not None and ctx.plan.flight_practicality == "low":
            itin.practicality = "low"
            itin.data_quality.append("Low practicality: long road transfer to or from the airport")
        return itin

    # ------------------------------------------------------------------ train / bus / transit
    def build_transit(self, option: NormalizedTransit, *, hotel: NormalizedHotel | None,
                      hotel_to_venue: NormalizedRoute | None = None, wheelchair_routed: bool = False) -> Itinerary | None:
        """Google Maps transit routes end at the venue. If they arrive before the mission day, the traveller
        goes to a hotel near the venue for the night and leaves in the morning (like a night-before flight)."""
        strategy = self.strategy_for_arrival(option.arrival_time)
        if strategy is None:
            return None
        ctx, a, req = self.ctx, self.a, self.ctx.request
        needs_hotel = strategy == "night_before" or req.hotel_required
        if needs_hotel and hotel is None:
            return None
        if strategy == "night_before" and hotel_to_venue is None:
            return None

        timeline: list[TimelineEvent] = []
        services = [s for s in option.segments if s.mode != "walk"]
        for index, seg in enumerate(option.segments):
            if seg.mode == "walk":
                continue
            word = MODE_WORD.get(seg.mode, "Transit")
            first = seg is services[0]
            nxt = option.segments[index + 1] if index + 1 < len(option.segments) else None
            timeline.append(TimelineEvent(
                time=seg.depart_at or option.departure_time, kind="board" if first else "change",
                title=f"Board {seg.name}" if first else f"Change to {seg.name}",
                detail=" · ".join(x for x in (seg.from_stop, seg.operator) if x) or None,
                duration_to_next_minutes=seg.duration_minutes, mode_to_next=f"{word}",
                distance_to_next_km=None))
            if nxt is not None and nxt.mode == "walk" and seg is not services[-1]:
                timeline.append(TimelineEvent(
                    time=seg.arrive_at or option.arrival_time, kind="transfer", title=f"Arrive {seg.to_stop or 'stop'}",
                    detail="Change here", duration_to_next_minutes=nxt.duration_minutes, mode_to_next="Walk"))
        last = services[-1]

        legs: list[GroundLeg] = []
        leave_hotel_at: datetime | None = None
        if strategy == "night_before":
            # Arrive near the venue the evening before → short taxi to the hotel → morning taxi to the venue
            assert hotel is not None and hotel_to_venue is not None
            timeline.append(TimelineEvent(
                time=option.arrival_time, kind="transfer", title=f"Arrive near {ctx.venue.name}",
                detail=f"Last stop: {last.to_stop}" if last.to_stop else None,
                duration_to_next_minutes=hotel_to_venue.duration_minutes, mode_to_next="Taxi",
                distance_to_next_km=hotel_to_venue.distance_km))
            to_hotel = self._leg(hotel_to_venue, option.arrival_time, "venue", "hotel", "before",
                                 from_label=ctx.venue.name, to_label=hotel.name)
            planned_buffer = ctx.required_buffer + a.night_before_extra_margin_minutes
            venue_arrival = ctx.deadline - timedelta(minutes=planned_buffer)
            leave_hotel_at = venue_arrival - timedelta(minutes=hotel_to_venue.duration_minutes)
            to_venue = self._leg(hotel_to_venue, leave_hotel_at, "hotel", "venue", "mission")
            legs = [to_hotel, to_venue]
            nights_before = (ctx.mission_date - option.arrival_time.date()).days
            timeline += [
                TimelineEvent(time=to_hotel.arrive_at, kind="hotel", title=f"Check in at {hotel.name}",
                              detail="Overnight stay" if nights_before <= 1 else f"{nights_before} nights before your mission",
                              mode_to_next="Overnight"),
                TimelineEvent(time=leave_hotel_at, kind="leave", title="Leave the hotel",
                              detail=f"Planned for a {planned_buffer}-minute buffer",
                              duration_to_next_minutes=to_venue.duration_minutes, mode_to_next="Taxi",
                              distance_to_next_km=to_venue.distance_km)]
        else:
            venue_arrival = option.arrival_time
            if hotel is not None:
                timeline.append(TimelineEvent(time=last.arrive_at or option.arrival_time, kind="transfer",
                                              title=f"Arrive {last.to_stop or 'final stop'}",
                                              detail=f"Room for tonight at {hotel.name}"))

        # Mission-day ground = local transit/walking after the long-distance service (same day) + hotel taxi
        local = [s for s in option.segments if s.mode in ("walk", "metro", "bus") and s.duration_minutes < 90
                 and s.depart_at and s.depart_at >= (last.arrive_at or option.arrival_time) - timedelta(minutes=1)]
        local_minutes = sum(s.duration_minutes for s in local)
        mission_local = local_minutes if strategy == "same_day" else 0
        before_local = local_minutes if strategy == "night_before" else 0

        travelers = req.travelers
        long_km = option.distance_km or 0
        local_services = [s for s in services if s.duration_minutes < 90]
        reported = option.fare_source == "google_search_transport_options"
        if option.fare is not None:
            ticket, ticket_source = option.fare * travelers, "live"
            if option.source == "demo" or option.fare_source == "demo":
                ticket_detail = "Fare from the demo dataset"
            elif reported:
                # The reported fare covers the long-distance service; city connections are added as estimates
                local_fare = a.local_transit_fare * len(local_services) * travelers
                ticket += local_fare
                seller = f" (listed by {option.fare_seller})" if option.fare_seller else ""
                ticket_detail = (f"Fare shown by Google Search{seller}"
                                 + (f" + ≈{fmt_money(local_fare, ctx.currency)} estimated for local connections"
                                    if local_fare else "") + " — check availability before booking")
            else:
                ticket_detail = "Fare reported by Google Maps"
        else:
            per_km = a.train_fare_per_km if option.mode == "train" else a.bus_fare_per_km
            fare = max(a.train_min_fare, per_km * long_km) + a.local_transit_fare * len(local_services)
            ticket, ticket_source = fare * travelers, "estimated"
            klass = "3AC" if option.mode == "train" else "AC sleeper" if option.mode == "bus" else "standard"
            symbol = "₹" if ctx.currency == "INR" else f"{ctx.currency} "
            ticket_detail = (f"≈ {klass} fare for {long_km:,.0f} km at {symbol}{per_km:g}/km — "
                             f"estimated, not a live fare" + (f" · {travelers} travellers" if travelers > 1 else ""))

        check_in, check_out, nights, hotel_cost, hotel_source = self._hotel_stay(strategy, option.arrival_time, hotel)
        word = {"train": "Train", "bus": "Bus"}.get(option.mode, "Transit")
        cost = self._costs(ticket=ticket, ticket_source=ticket_source,
                           ticket_label=f"{word} ticket" if ticket_source == "live" else f"{word} fare (estimated)",
                           ticket_detail=ticket_detail, legs=legs, hotel=hotel, hotel_cost=hotel_cost,
                           hotel_source=hotel_source, nights=nights, departure=option.departure_time)

        quality = [f"{word} fare estimated (Google Maps returns schedules, not fares)"] if ticket_source == "estimated" else []
        quality += [f"{l.from_label} → {l.to_label} time estimated from distance" for l in legs if l.estimated]
        if hotel is not None and hotel_cost is None:
            quality.append("Hotel price not available")

        main = MainLeg(
            mode=option.mode, provider=option.provider, title=option.title,  # type: ignore[arg-type]
            references=[s.name.split(" ", 1)[0] for s in services if s.name[:1].isdigit()],
            departure_label=services[0].from_stop or ctx.origin.city, arrival_label=last.to_stop or ctx.destination.city,
            departure_time=option.departure_time, arrival_time=option.arrival_time,
            duration_minutes=option.duration_minutes, stops=sum(s.stops_count for s in services),
            transfers=option.transfers, distance_km=option.distance_km, schedule_source="live",
            data_source="Demo dataset" if option.source == "demo" else
            "Google Maps transit · fare from Google Search" if reported else "Google Maps transit",
            fare_label="Fare" if ticket_source == "live" else "Estimated fare",
            note=("Train schedule from Google Maps transit. Not a booking — seat availability, fares and live "
                  "running status aren't confirmed." if option.mode == "train" else
                  ("Bus schedule from Google Maps transit with the fare Google Search shows. Not a confirmed "
                   "ticket — check the operator for seats." if reported else
                   "Estimated bus/transit route from Google Maps transit. Not a confirmed ticket — check the "
                   "operator for seats and fares.")))
        total_travel = option.duration_minutes + sum(l.duration_minutes for l in legs)
        ident = f"{'nb' if strategy == 'night_before' else 'sd'}-{option.mode}-{option.id.removeprefix('t-')[:8]}-{self._hotel_key(hotel)}"
        return self._finish(
            ident=ident, mode=option.mode, strategy=strategy, main=main, legs=legs, timeline=timeline,
            venue_arrival=venue_arrival, departure=option.departure_time, cost=cost, hotel=hotel, check_in=check_in,
            check_out=check_out, leave_hotel_at=leave_hotel_at, total_travel=total_travel,
            extra_mission_ground=mission_local, extra_before_ground=before_local, quality=quality,
            confidence="medium" if ticket_source == "estimated" else "high", transit=option,
            wheelchair_routed=wheelchair_routed)

    # ------------------------------------------------------------------ ground (drive all the way)
    def build_ground(self, route: NormalizedRoute, *, hotel: NormalizedHotel | None) -> Itinerary | None:
        """A one-way outstation cab from the origin city straight to the venue, timed to arrive with the
        required buffer plus a margin. Route is live (Google Maps); the fare is estimated."""
        ctx, a, req = self.ctx, self.a, self.ctx.request
        if req.hotel_required and hotel is None:
            return None
        planned_buffer = ctx.required_buffer + a.night_before_extra_margin_minutes
        venue_arrival = ctx.deadline - timedelta(minutes=planned_buffer)
        traffic = max(0, (route.typical_max_minutes or route.duration_minutes) - route.duration_minutes)
        departure = venue_arrival - timedelta(minutes=route.duration_minutes + traffic)
        drive_days = max(1, math.ceil(route.duration_minutes / (8 * 60)))
        cabs = math.ceil(req.travelers / 4)
        fare = (a.outstation_cab_per_km * route.distance_km + a.driver_allowance_per_day * drive_days) * cabs
        timeline = [TimelineEvent(
            time=departure, kind="depart", title=f"Leave {ctx.origin.city} by cab",
            detail=f"Door to door · {route.via}" if route.via else "Door to door",
            duration_to_next_minutes=route.duration_minutes + traffic, mode_to_next="Outstation cab",
            distance_to_next_km=route.distance_km)]
        check_in, check_out, nights, hotel_cost, hotel_source = self._hotel_stay("same_day", venue_arrival, hotel)
        cost = self._costs(
            ticket=fare, ticket_source="estimated", ticket_label="Outstation cab",
            ticket_detail=f"≈ {'₹' if ctx.currency == 'INR' else ctx.currency + ' '}{a.outstation_cab_per_km:g}/km × "
                          f"{route.distance_km:,.0f} km + "
                          f"driver allowance — estimated", legs=[], hotel=hotel, hotel_cost=hotel_cost,
            hotel_source=hotel_source, nights=nights, departure=departure)
        main = MainLeg(
            mode="ground", provider="Outstation cab", title=f"Drive {route.distance_km:,.0f} km",
            departure_label=ctx.origin.city, arrival_label=ctx.venue.name, departure_time=departure,
            arrival_time=venue_arrival, duration_minutes=route.duration_minutes + traffic,
            distance_km=route.distance_km, schedule_source="estimated" if route.estimated else "live",
            data_source="Demo dataset" if route.source == "demo" else "Google Maps route",
            fare_label="Estimated fare",
            note="Road route and time from Google Maps; departure planned to absorb typical traffic."
            if not route.estimated else "Road time estimated from distance; departure planned with a traffic margin.")
        quality = ["Cab fare estimated"] + (["Drive time estimated from distance"] if route.estimated else [])
        return self._finish(
            ident=f"sd-ground-{int(route.distance_km)}-{self._hotel_key(hotel)}", mode="ground", strategy="same_day",
            main=main, legs=[], timeline=timeline, venue_arrival=venue_arrival, departure=departure, cost=cost,
            hotel=hotel, check_in=check_in, check_out=check_out, leave_hotel_at=None,
            total_travel=route.duration_minutes + traffic, extra_mission_ground=route.duration_minutes + traffic,
            quality=quality, confidence="medium")
