"""Provider-independent travel models. Nothing outside integrations/ sees raw SerpApi JSON.

All datetimes are naive *local* times at the airport/place they refer to (Google Flights reports
local times, and the arrival deadline is local to the destination).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GeoPoint(BaseModel):
    lat: float
    lng: float

    def as_param(self) -> str:
        return f"{self.lat:.6f},{self.lng:.6f}"


class Airport(BaseModel):
    code: str
    city: str
    name: str
    country: str
    location: GeoPoint


class NearbyHub(BaseModel):
    """A transport hub (airport, railway station, bus point) relative to a resolved location."""

    kind: Literal["airport", "railway_station", "bus_point"]
    code: str | None = None
    name: str
    city: str
    location: GeoPoint | None = None
    distance_km: float | None = None       # straight line to the location it serves
    road_km: float | None = None            # estimated road distance
    transfer_minutes: int | None = None     # estimated road transfer time
    practical: bool = True


class ResolvedLocation(BaseModel):
    """A place a traveller typed (city, town or landmark) — independent of whether it has an airport.

    `code` is the IATA code of the city's own commercial airport, or None. Fields `city`, `name`,
    `country` and `location` intentionally mirror `Airport` so journey text and maps work for both."""

    query: str
    city: str
    name: str
    country: str = "IN"
    location: GeoPoint
    code: str | None = None
    has_airport: bool = False
    airports: list[Airport] = Field(default_factory=list)
    nearby_airports: list[NearbyHub] = Field(default_factory=list)
    railway_stations: list[str] = Field(default_factory=list)
    bus_points: list[str] = Field(default_factory=list)
    source: Literal["airport", "reference", "geocoded", "demo"] = "reference"


class FlightSegment(BaseModel):
    airline: str
    flight_number: str
    departure_airport: str
    departure_airport_name: str | None = None
    arrival_airport: str
    arrival_airport_name: str | None = None
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    often_delayed: bool = False
    airplane: str | None = None


class Layover(BaseModel):
    airport: str
    airport_name: str | None = None
    duration_minutes: int
    overnight: bool = False


class NormalizedFlight(BaseModel):
    id: str
    airline: str
    airline_logo: str | None = None
    flight_numbers: list[str]
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    stops: int
    layovers: list[Layover] = Field(default_factory=list)
    segments: list[FlightSegment] = Field(default_factory=list)
    price: float | None = None  # per traveller as returned by the provider for `adults`
    currency: str = "INR"
    often_delayed: bool = False
    booking_token: str | None = None
    source: str = "google_flights"

    @property
    def min_layover_minutes(self) -> int | None:
        return min((lay.duration_minutes for lay in self.layovers), default=None)


class ReviewAspect(BaseModel):
    name: str
    positive: int = 0
    negative: int = 0
    neutral: int = 0
    total: int = 0


class NormalizedHotel(BaseModel):
    id: str
    name: str
    rating: float | None = None
    reviews: int | None = None
    price_per_night: float | None = None
    total_price: float | None = None
    currency: str = "INR"
    location: GeoPoint | None = None
    address: str | None = None
    amenities: list[str] = Field(default_factory=list)
    image: str | None = None
    images: list[str] = Field(default_factory=list)
    hotel_class: int | None = None
    free_cancellation: bool | None = None
    review_breakdown: list[ReviewAspect] = Field(default_factory=list)
    link: str | None = None
    check_in_time: str | None = None
    check_out_time: str | None = None
    distance_km: float | None = None  # to venue, filled by the mission engine
    source: str = "google_hotels"


class NormalizedRoute(BaseModel):
    origin_label: str
    destination_label: str
    distance_km: float
    duration_minutes: int
    typical_max_minutes: int | None = None
    mode: str = "Driving"
    via: str | None = None
    estimated: bool = False  # True when computed from straight-line distance (no live route)
    source: str = "google_maps_directions"


class NormalizedPlace(BaseModel):
    id: str
    name: str
    category: str | None = None
    rating: float | None = None
    reviews: int | None = None
    address: str | None = None
    location: GeoPoint | None = None
    distance_km: float | None = None
    hours: str | None = None
    thumbnail: str | None = None
    price: str | None = None
    data_id: str | None = None
    place_id: str | None = None
    source: str = "google_local"


class NormalizedReview(BaseModel):
    rating: float | None = None
    text: str
    date: str | None = None
    author: str | None = None


class ReviewTopic(BaseModel):
    keyword: str
    mentions: int


class ReviewBundle(BaseModel):
    place: NormalizedPlace | None = None
    reviews: list[NormalizedReview] = Field(default_factory=list)
    topics: list[ReviewTopic] = Field(default_factory=list)
    source: str = "google_maps_reviews"


class ExploreDestination(BaseModel):
    name: str
    country: str | None = None
    airport: str | None = None
    flight_price: float | None = None
    hotel_price: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    stops: int | None = None
    flight_duration_minutes: int | None = None
    thumbnail: str | None = None


class TransitSegment(BaseModel):
    """One leg of a public-transport journey as returned by Google Maps transit."""

    mode: str  # train | bus | metro | walk | ferry | other
    name: str
    operator: str | None = None
    from_stop: str | None = None
    to_stop: str | None = None
    depart_at: datetime | None = None
    arrive_at: datetime | None = None
    duration_minutes: int
    stops_count: int = 0
    distance_km: float | None = None


class NormalizedTransit(BaseModel):
    """A public-transport option (train / bus / transit). Schedules are live from Google Maps; Google Maps
    returns no fares for Indian long-distance services, so `fare` is usually None (estimated later)."""

    id: str
    mode: str  # train | bus | transit
    title: str
    provider: str | None = None
    departure_time: datetime
    arrival_time: datetime
    duration_minutes: int
    distance_km: float | None = None
    transfers: int = 0
    walking_minutes: int = 0
    long_distance_minutes: int = 0
    segments: list[TransitSegment] = Field(default_factory=list)
    fare: float | None = None
    currency: str | None = None
    source: str = "google_maps_directions"
    # Where `fare` came from: "google_maps" (Maps transit reported it), "google_search_transport_options"
    # (matched to a Google Search transport-options route) or "demo". None = no fare (estimated later).
    fare_source: str | None = None
    fare_seller: str | None = None  # ticket seller named by the source, e.g. "IRCTC" — never a booking


class ReportedTransportRoute(BaseModel):
    """One route from Google Search's "transport options" answer box (SerpApi engine=google,
    answer_box.type == "transport_options"). Clock times only; the fare is what Google shows, or None."""

    mode: str | None = None          # train | bus | None when the box doesn't say
    depart_clock: tuple[int, int] | None = None
    arrive_clock: tuple[int, int] | None = None
    duration_minutes: int | None = None
    changes: int | None = None
    fare: float | None = None
    currency: str | None = None
    numbers: list[str] = Field(default_factory=list)    # service numbers, e.g. ["12919"]
    operators: list[str] = Field(default_factory=list)
    sellers: list[str] = Field(default_factory=list)    # ticket providers listed by Google
