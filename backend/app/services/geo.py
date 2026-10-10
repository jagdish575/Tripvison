"""Geographic helpers: great-circle distance and a conservative road-time estimate."""

from __future__ import annotations

import math

from app.schemas.travel import GeoPoint, NormalizedRoute

ROAD_FACTOR = 1.35  # road distance / straight-line distance in Indian cities (conservative)


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    r = 6371.0088
    phi1, phi2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def estimate_drive_minutes(road_km: float) -> int:
    speed = 14.0 if road_km < 5 else 22.0 if road_km < 15 else 32.0 if road_km < 100 else 55.0  # km/h
    return max(6, int(round(road_km / speed * 60)))


def estimate_route(a: GeoPoint, b: GeoPoint, origin_label: str, destination_label: str) -> NormalizedRoute:
    """Fallback when live directions are unavailable. Always flagged `estimated=True`."""
    road_km = max(0.5, round(haversine_km(a, b) * ROAD_FACTOR, 1))
    minutes = estimate_drive_minutes(road_km)
    return NormalizedRoute(
        origin_label=origin_label,
        destination_label=destination_label,
        distance_km=road_km,
        duration_minutes=minutes,
        typical_max_minutes=int(round(minutes * 1.35)),
        mode="Driving",
        estimated=True,
        source="estimate",
    )


def estimate_transfer_minutes(road_km: float) -> int:
    """Door-to-door road time for a hub transfer (city traffic for short hops, highway speed beyond ~40 km).
    Used to rank airports/hubs before any live routing; always shown to users as an estimate."""
    if road_km < 40:
        return estimate_drive_minutes(road_km)
    return int(round(10 + road_km / 48.0 * 60))


HIGHWAY_FACTOR = 1.2  # intercity roads are straighter than city streets


def road_km_estimate(a: GeoPoint, b: GeoPoint) -> float:
    straight = haversine_km(a, b)
    return round(straight * (HIGHWAY_FACTOR if straight > 40 else ROAD_FACTOR), 1)
