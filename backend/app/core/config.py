"""Application settings, loaded from environment variables / .env files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TripMission"
    version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # DEBUG_MODE=true exposes request counts, timings, cache hits and raw provider errors to the UI/API.
    # Never enable it for real users.
    debug_mode: bool = False

    # Data provider
    demo_mode: bool = False
    serpapi_api_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search.json"
    serpapi_timeout_seconds: float = 25.0
    serpapi_max_retries: int = 2
    serpapi_max_concurrency: int = 4
    serpapi_gl: str = "in"
    serpapi_hl: str = "en"

    # Storage
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'tripvision.db').as_posix()}"
    redis_url: str = ""

    # AI explanation (optional). Providers: "anthropic" or "euri" (OpenAI-compatible chat completions).
    ai_provider: str = "anthropic"
    ai_api_key: str = ""
    ai_model: str = "claude-opus-5-5"
    ai_model_fast: str = ""  # optional fallback model, tried if the main model fails
    ai_base_url: str = "https://api.euron.one/api/v1/euri"
    ai_timeout_seconds: float = 30.0

    # Email (optional). EMAIL_PROVIDER: auto | smtp | resend | preview
    email_provider: str = "auto"
    email_from: str = "TripMission <no-reply@tripmission.app>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = Field(default="", validation_alias=AliasChoices("SMTP_USER", "SMTP_USERNAME", "smtp_user"))
    smtp_from_email: str = ""  # optional sender address; used with the product name when set
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    resend_api_key: str = ""
    app_base_url: str = ""  # used for "View my journey" links; defaults to the first FRONTEND_URL
    reminder_hours_before: int = 24
    reminder_check_interval_seconds: int = 300

    # Authentication. Google Identity Services ID tokens are verified server-side against GOOGLE_CLIENT_ID.
    # GOOGLE_CLIENT_SECRET is only needed for an authorization-code flow and is never sent to the browser.
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""          # HS256 key for session tokens; random per process when empty (dev only)
    session_ttl_hours: int = 24 * 14
    session_cookie_name: str = "tm_session"
    session_cookie_secure: bool | None = None  # None = auto (True when APP_BASE_URL/FRONTEND_URL is https)
    auth_required: bool = True        # missions need a signed-in (Google or demo) session
    demo_login_enabled: bool = True   # "Continue in Demo Mode" for judges

    # HTTP
    frontend_url: str = "http://localhost:5173"
    max_request_bytes: int = 32 * 1024
    analyze_rate_limit_per_minute: int = 12
    search_rate_limit_per_minute: int = 30

    # Mission engine funnel
    flight_shortlist_per_strategy: int = 4
    hotel_shortlist_per_stay: int = 3
    max_hotels_for_directions: int = 4
    max_review_hotels: int = 2
    max_place_categories: int = 3
    max_hotel_distance_km: float = 40.0

    # Route intelligence (docs/LLD.md §Route intelligence)
    max_practical_airport_transfer_minutes: int = 180   # beyond this a nearby airport isn't used for flights
    low_practicality_airport_transfer_minutes: int = 90  # flight + transfer flagged LOW PRACTICALITY above this
    min_flight_distance_km: float = 200.0               # shorter trips skip flight searches entirely
    own_airport_radius_km: float = 35.0                 # an airport this close "belongs" to the city
    airport_checkin_minutes: int = 75                   # arrive this early for a domestic flight
    optional_timeout_seconds: float = 8.0               # places / reviews never block a mission longer than this

    # Journey assumptions (documented in SCORING_ENGINE.md)
    airport_exit_minutes: int = 25
    hotel_stop_minutes: int = 15
    night_before_extra_margin_minutes: int = 15
    taxi_base_fare: float = 100.0
    taxi_per_km: float = 18.0
    train_fare_per_km: float = 1.25
    bus_fare_per_km: float = 1.8
    outstation_cab_per_km: float = 13.0

    scoring_weights: dict[str, float] | None = Field(default=None)

    @field_validator("database_url", "ai_model", "ai_provider", "ai_base_url", mode="before")
    @classmethod
    def _blank_uses_default(cls, value: object, info) -> object:
        if value in (None, "") or (isinstance(value, str) and not value.strip()):
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("session_cookie_secure", mode="before")
    @classmethod
    def _blank_is_auto(cls, value: object) -> object:
        return None if value in (None, "") else value

    @field_validator("scoring_weights", mode="before")
    @classmethod
    def _parse_weights(cls, value: object) -> object:
        if value in (None, ""):
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_url.split(",") if o.strip()]

    @property
    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_api_key.strip())

    @property
    def ai_configured(self) -> bool:
        return bool(self.ai_api_key.strip())

    @property
    def database_kind(self) -> str:
        return "postgresql" if self.database_url.startswith("postgresql") else "sqlite"

    @property
    def public_base_url(self) -> str:
        return (self.app_base_url or (self.cors_origins[0] if self.cors_origins else "http://localhost:5173")).rstrip("/")

    @property
    def google_auth_configured(self) -> bool:
        return bool(self.google_client_id.strip())

    @property
    def cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.public_base_url.startswith("https://")

    @property
    def sender(self) -> str:
        """SMTP_FROM_EMAIL (e.g. the Gmail account itself) wins over the EMAIL_FROM default — Gmail rewrites
        foreign From addresses anyway."""
        if self.smtp_from_email.strip():
            return f"{self.app_name} <{self.smtp_from_email.strip()}>"
        return self.email_from

    def secret_values(self) -> list[str]:
        return [s for s in (self.serpapi_api_key, self.ai_api_key, self.smtp_password, self.resend_api_key,
                            self.google_client_secret, self.session_secret) if s and len(s) >= 6]


@lru_cache
def get_settings() -> Settings:
    return Settings()
