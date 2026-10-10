"""Users, their preferences and saved missions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """A Google-authenticated traveller, or an anonymous demo session (`is_demo`)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="Traveller")
    picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UserPreference(Base):
    """Email, notification and travel defaults. One row per user, created on first sign-in."""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # email preferences
    email_trip_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    email_departure_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    email_journey_changes: Mapped[bool] = mapped_column(Boolean, default=True)
    email_price_changes: Mapped[bool] = mapped_column(Boolean, default=False)
    # notification preferences
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # travel preferences (defaults for new missions)
    home_city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_priority: Mapped[str] = mapped_column(String(16), default="balanced")
    default_modes: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["flight", "train", "bus", "ground"])
    default_buffer_minutes: Mapped[int] = mapped_column(Integer, default=60)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": {"trip_summary": self.email_trip_summary, "departure_reminder": self.email_departure_reminder,
                      "journey_changes": self.email_journey_changes, "price_changes": self.email_price_changes},
            "notifications": {"enabled": self.notifications_enabled},
            "travel": {"home_city": self.home_city, "priority": self.default_priority,
                       "modes": list(self.default_modes or []), "buffer_minutes": self.default_buffer_minutes},
        }


class SavedMission(Base):
    __tablename__ = "saved_missions"
    __table_args__ = (UniqueConstraint("user_id", "mission_id", name="uq_saved_mission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
