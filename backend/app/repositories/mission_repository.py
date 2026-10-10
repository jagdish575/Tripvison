"""All database access for missions and their derived records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import (FlightOption, HotelOption, Itinerary, Mission, MissionPreference, Place, Recommendation,
                        Review, TravelOption)
from app.schemas.mission import MissionRequest
from app.schemas.result import MissionResult


class MissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, request: MissionRequest, *, mode: str, origin_code: str | None, destination_code: str | None,
               user_id: str | None = None) -> Mission:
        mission = Mission(
            status="queued", mode=mode, mission_type=str(request.mission_type), user_id=user_id,
            origin_query=request.origin, destination_query=request.destination, venue_query=request.venue,
            origin_airport=origin_code, destination_airport=destination_code, travel_date=request.travel_date,
            arrival_deadline=request.arrival_deadline, travelers=request.travelers, budget=request.budget,
            currency=request.currency, progress={"stage": "queued", "completed": [], "counts": {}, "message": "Queued"},
            request=request.model_dump(mode="json"),
        )
        mission.preference = MissionPreference(
            min_buffer_minutes=request.min_buffer_minutes, max_ground_minutes=request.max_ground_minutes,
            hotel_required=request.hotel_required, min_hotel_rating=request.min_hotel_rating,
            max_stops=request.max_stops, allow_previous_day=request.allow_previous_day,
            preferences=[str(p) for p in request.preferences], priority=str(request.priority),
            modes=[str(m) for m in request.modes], stay_nights=request.stay_nights,
            food_per_day=request.food_per_day, accessibility=[str(a) for a in request.accessibility],
        )
        self.session.add(mission)
        self.session.flush()
        return mission

    def get(self, mission_id: str) -> Mission | None:
        return self.session.get(Mission, mission_id)

    def set_progress(self, mission_id: str, progress: dict[str, Any], status: str = "running") -> None:
        self.session.execute(update(Mission).where(Mission.id == mission_id)
                             .values(progress=progress, status=status, updated_at=datetime.now(timezone.utc)))

    def fail(self, mission_id: str, code: str, message: str) -> None:
        self.session.execute(update(Mission).where(Mission.id == mission_id).values(
            status="failed", error={"code": code, "message": message}, updated_at=datetime.now(timezone.utc)))

    def fail_interrupted(self) -> int:
        result = self.session.execute(
            update(Mission).where(Mission.status.in_(["queued", "running"])).values(
                status="failed",
                error={"code": "interrupted", "message": "The analysis was interrupted by a server restart. Please run it again."}))
        return result.rowcount or 0

    def reset_derived(self, mission_id: str) -> None:
        """Remove analysis rows before storing a re-check (subscriptions and sent emails are kept)."""
        for model in (Recommendation, Itinerary, Review, Place, HotelOption, FlightOption, TravelOption):
            self.session.execute(delete(model).where(model.mission_id == mission_id))
        self.session.flush()

    def recent(self, limit: int = 20) -> list[Mission]:
        return list(self.session.scalars(select(Mission).order_by(Mission.created_at.desc()).limit(limit)))

    def for_user(self, user_id: str, limit: int = 100) -> list[Mission]:
        return list(self.session.scalars(select(Mission).where(Mission.user_id == user_id)
                                         .order_by(Mission.created_at.desc()).limit(limit)))

    def complete(self, mission_id: str, result: MissionResult, artifacts: Any, progress: dict[str, Any]) -> None:
        mission = self.get(mission_id)
        if mission is None:
            return
        flight_rows: dict[str, str] = {}
        for flight, strategy, shortlisted in artifacts.flights:
            row = FlightOption(
                mission_id=mission_id, external_id=flight.id, airline=flight.airline[:120],
                flight_numbers=flight.flight_numbers, departure_airport=flight.departure_airport,
                arrival_airport=flight.arrival_airport, departure_time=flight.departure_time,
                arrival_time=flight.arrival_time, duration_minutes=flight.duration_minutes, stops=flight.stops,
                price=flight.price, currency=flight.currency, often_delayed=flight.often_delayed,
                strategy=strategy, shortlisted=shortlisted, data=flight.model_dump(mode="json"))
            self.session.add(row)
            self.session.flush()
            flight_rows[flight.id] = row.id

        travel_rows: dict[str, str] = {}
        for option, shortlisted in getattr(artifacts, "transit", []):
            row = TravelOption(
                mission_id=mission_id, external_id=option.id, mode=option.mode, title=option.title[:300],
                provider=(option.provider or "")[:200] or None, departure_time=option.departure_time,
                arrival_time=option.arrival_time, duration_minutes=option.duration_minutes,
                transfers=option.transfers, distance_km=option.distance_km, fare=option.fare,
                fare_source="live" if option.fare is not None else "estimated",
                schedule_source=option.source, data={**option.model_dump(mode="json"), "shortlisted": shortlisted})
            self.session.add(row)
            self.session.flush()
            travel_rows[option.id] = row.id
        ground = getattr(artifacts, "ground", None)
        if ground is not None:
            ground_itins = [i for i in artifacts.itineraries if i.mode == "ground"]
            ref = ground_itins[0] if ground_itins else None
            row = TravelOption(
                mission_id=mission_id, external_id=f"ground-{int(ground.distance_km)}", mode="ground",
                title=f"Drive {ground.distance_km:,.0f} km", provider="Outstation cab",
                departure_time=ref.main.departure_time if ref else datetime.now(),
                arrival_time=ref.main.arrival_time if ref else datetime.now(),
                duration_minutes=ground.duration_minutes, transfers=0, distance_km=ground.distance_km,
                fare=None, fare_source="estimated", schedule_source=ground.source, data=ground.model_dump(mode="json"))
            self.session.add(row)
            self.session.flush()
            travel_rows["ground"] = row.id

        hotel_rows: dict[tuple[str, str], str] = {}
        hotel_by_external: dict[str, str] = {}
        for hotel, check_in, check_out, shortlisted in artifacts.hotels:
            row = HotelOption(
                mission_id=mission_id, external_id=hotel.id[:200], name=hotel.name[:200], rating=hotel.rating,
                review_count=hotel.reviews, price_per_night=hotel.price_per_night, total_price=hotel.total_price,
                currency=hotel.currency, latitude=hotel.location.lat if hotel.location else None,
                longitude=hotel.location.lng if hotel.location else None, distance_km=hotel.distance_km,
                check_in_date=check_in, check_out_date=check_out, shortlisted=shortlisted,
                data=hotel.model_dump(mode="json"))
            self.session.add(row)
            self.session.flush()
            hotel_rows[(hotel.id, check_in.isoformat())] = row.id
            hotel_by_external.setdefault(hotel.id, row.id)

        for hotel_id, reviews in artifacts.reviews.items():
            for review in reviews:
                self.session.add(Review(mission_id=mission_id, hotel_option_id=hotel_by_external.get(hotel_id),
                                        source="google_maps_reviews" if result.mode == "live" else "demo",
                                        rating=review.rating, text=review.text, published=review.date,
                                        author=review.author))

        for group in result.places:
            for place in group.items:
                self.session.add(Place(
                    mission_id=mission_id, category=group.category, name=place.name[:200], rating=place.rating,
                    review_count=place.reviews, address=(place.address or "")[:300] or None,
                    latitude=place.location.lat if place.location else None,
                    longitude=place.location.lng if place.location else None, distance_km=place.distance_km,
                    data=place.model_dump(mode="json")))

        itinerary_rows: dict[str, Itinerary] = {}
        for itin in artifacts.itineraries:
            hotel_key = (itin.hotel.id, itin.hotel_check_in.isoformat()) if itin.hotel and itin.hotel_check_in else None
            row = Itinerary(
                id=itin.id, mission_id=mission_id, mode=itin.mode,
                flight_option_id=flight_rows.get(itin.flight.id) if itin.flight else None,
                travel_option_id=travel_rows.get(itin.transit.id) if itin.transit else
                travel_rows.get("ground") if itin.mode == "ground" else None,
                hotel_option_id=hotel_rows.get(hotel_key) if hotel_key else None, strategy=itin.strategy,
                total_cost=itin.cost.total, venue_arrival=itin.arrival.venue_arrival,
                buffer_minutes=itin.arrival.buffer_minutes, overall_score=itin.scores.overall if itin.scores else 0,
                risk_level=itin.risk.level if itin.risk else "HIGH", risk_score=itin.risk.score if itin.risk else 100,
                feasible=bool(itin.constraints and itin.constraints.feasible),
                satisfies_constraints=bool(itin.constraints and itin.constraints.all_ok),
                data=itin.model_dump(mode="json"))
            self.session.add(row)
            itinerary_rows[itin.id] = row
        self.session.flush()

        for category, itin_id in result.categories.items():
            row = itinerary_rows.get(itin_id)
            if row is None:
                continue
            is_rec = category == "recommended" and result.explanation is not None
            self.session.add(Recommendation(
                mission_id=mission_id, category=category, itinerary_pk=row.pk,
                explanation=result.explanation.text if is_rec else None,
                explanation_source=result.explanation.source if is_rec else None))

        mission.status = "complete"
        mission.result = result.model_dump(mode="json")
        mission.progress = progress
        mission.error = None
