"""ORM models for missions and everything derived from a mission analysis."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric,
                        String, Text, Time, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    mode: Mapped[str] = mapped_column(String(8))
    mission_type: Mapped[str] = mapped_column(String(16))
    origin_query: Mapped[str] = mapped_column(String(120))
    destination_query: Mapped[str] = mapped_column(String(120))
    venue_query: Mapped[str | None] = mapped_column(String(200), nullable=True)
    origin_airport: Mapped[str | None] = mapped_column(String(3), nullable=True)
    destination_airport: Mapped[str | None] = mapped_column(String(3), nullable=True)
    travel_date: Mapped[date] = mapped_column(Date)
    arrival_deadline: Mapped[time] = mapped_column(Time)
    travelers: Mapped[int] = mapped_column(Integer, default=1)
    budget: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    request: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    client_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Owner. NULL for missions created before sign-in existed; those are not readable through the API.
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    preference: Mapped[MissionPreference | None] = relationship(
        back_populates="mission", uselist=False, cascade="all, delete-orphan")
    flights: Mapped[list[FlightOption]] = relationship(cascade="all, delete-orphan")
    hotels: Mapped[list[HotelOption]] = relationship(cascade="all, delete-orphan")
    places: Mapped[list[Place]] = relationship(cascade="all, delete-orphan")
    itineraries: Mapped[list[Itinerary]] = relationship(cascade="all, delete-orphan")
    recommendations: Mapped[list[Recommendation]] = relationship(cascade="all, delete-orphan")


class MissionPreference(Base):
    __tablename__ = "mission_preferences"

    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), primary_key=True)
    min_buffer_minutes: Mapped[int] = mapped_column(Integer)
    max_ground_minutes: Mapped[int] = mapped_column(Integer)
    hotel_required: Mapped[bool] = mapped_column(Boolean)
    min_hotel_rating: Mapped[float] = mapped_column(Float)
    max_stops: Mapped[int] = mapped_column(Integer)
    allow_previous_day: Mapped[bool] = mapped_column(Boolean)
    preferences: Mapped[list[str]] = mapped_column(JSON, default=list)
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    modes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    stay_nights: Mapped[int | None] = mapped_column(Integer, nullable=True)
    food_per_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    accessibility: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    mission: Mapped[Mission] = relationship(back_populates="preference")


class FlightOption(Base):
    __tablename__ = "flight_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(120))
    airline: Mapped[str] = mapped_column(String(120))
    flight_numbers: Mapped[list[str]] = mapped_column(JSON, default=list)
    departure_airport: Mapped[str] = mapped_column(String(8))
    arrival_airport: Mapped[str] = mapped_column(String(8))
    departure_time: Mapped[datetime] = mapped_column(DateTime)
    arrival_time: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    stops: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    often_delayed: Mapped[bool] = mapped_column(Boolean, default=False)
    strategy: Mapped[str] = mapped_column(String(16))
    shortlisted: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class HotelOption(Base):
    __tablename__ = "hotel_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_per_night: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    check_in_date: Mapped[date] = mapped_column(Date)
    check_out_date: Mapped[date] = mapped_column(Date)
    shortlisted: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)

    reviews: Mapped[list[Review]] = relationship(cascade="all, delete-orphan")


class Place(Base):
    __tablename__ = "places"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    hotel_option_id: Mapped[str | None] = mapped_column(
        ForeignKey("hotel_options.id", ondelete="CASCADE"), nullable=True)
    source: Mapped[str] = mapped_column(String(40))
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    published: Mapped[str | None] = mapped_column(String(60), nullable=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)


class TravelOption(Base):
    """Non-flight options: trains, buses and public transport (Google Maps transit) and road trips."""

    __tablename__ = "travel_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(300))
    provider: Mapped[str | None] = mapped_column(String(200), nullable=True)
    departure_time: Mapped[datetime] = mapped_column(DateTime)
    arrival_time: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    transfers: Mapped[int] = mapped_column(Integer, default=0)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    fare: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    fare_source: Mapped[str] = mapped_column(String(16))
    schedule_source: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"
    __table_args__ = (UniqueConstraint("mission_id", "email", name="uq_subscription_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    trip_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    changes: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    departure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # local time of the journey
    utc_offset_minutes: Mapped[int] = mapped_column(Integer, default=330)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # last journey facts (change detection)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # summary | reminder | change
    to_email: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(300))
    html: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))  # sent | preview | failed
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Itinerary(Base):
    __tablename__ = "itineraries"
    __table_args__ = (Index("ix_itineraries_mission_score", "mission_id", "overall_score"),)

    pk: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    id: Mapped[str] = mapped_column(String(80))
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"))
    flight_option_id: Mapped[str | None] = mapped_column(
        ForeignKey("flight_options.id", ondelete="SET NULL"), nullable=True)
    travel_option_id: Mapped[str | None] = mapped_column(
        ForeignKey("travel_options.id", ondelete="SET NULL"), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    hotel_option_id: Mapped[str | None] = mapped_column(
        ForeignKey("hotel_options.id", ondelete="SET NULL"), nullable=True)
    strategy: Mapped[str] = mapped_column(String(16))
    total_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    venue_arrival: Mapped[datetime] = mapped_column(DateTime)
    buffer_minutes: Mapped[int] = mapped_column(Integer)
    overall_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(8))
    risk_score: Mapped[int] = mapped_column(Integer)
    feasible: Mapped[bool] = mapped_column(Boolean)
    satisfies_constraints: Mapped[bool] = mapped_column(Boolean)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("mission_id", "category", name="uq_recommendation_category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(16))
    itinerary_pk: Mapped[str] = mapped_column(ForeignKey("itineraries.pk", ondelete="CASCADE"))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
