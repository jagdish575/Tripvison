"""DEMO MODE — second scenario: Indore → Ujjain, visiting Mahakal Mandir (Shri Mahakaleshwar temple).

Shows airport-less routing: Ujjain has no commercial airport, the trip is short, so TripMission compares
train, bus and road instead of flights. Hotel, café and service names are fictional and illustrative;
schedules are generated relative to the requested arrival time and are NOT real timetables. Nothing
here is presented as live data — every result is labelled demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

CITY = "ujjain"

PLACES = {
    "mahakal mandir": ("Mahakal Mandir", "Jaisinghpura, Ujjain, Madhya Pradesh 456006", 23.1828, 75.7682),
    "mahakal": ("Mahakal Mandir", "Jaisinghpura, Ujjain, Madhya Pradesh 456006", 23.1828, 75.7682),
    "mahakaleshwar": ("Mahakal Mandir", "Jaisinghpura, Ujjain, Madhya Pradesh 456006", 23.1828, 75.7682),
    "mahakaleshwar temple": ("Mahakal Mandir", "Jaisinghpura, Ujjain, Madhya Pradesh 456006", 23.1828, 75.7682),
    "ram ghat": ("Ram Ghat", "Ram Ghat Marg, Ujjain", 23.1795, 75.7650),
    "ujjain city centre": ("Ujjain city centre", "Ujjain, Madhya Pradesh", 23.1793, 75.7849),
    "ujjain": ("Ujjain city centre", "Ujjain, Madhya Pradesh", 23.1793, 75.7849),
}

HOTELS = [
    {
        "id": "demo-ujn-shipra", "name": "Shipra Riverside Residency", "lat": 23.1810, "lng": 75.7660,
        "rating": 4.2, "reviews": 1320, "price": 2400, "class": 3, "free_cancellation": True,
        "address": "Near Ram Ghat, Ujjain", "image": None,
        "amenities": ["Free Wi-Fi", "Breakfast", "Air conditioning", "Elevator"],
        "breakdown": [("Location", 380, 12), ("Cleanliness", 210, 34), ("Service", 190, 21)],
    },
    {
        "id": "demo-ujn-mahakal-lok", "name": "Mahakal Lok Guest House", "lat": 23.1840, "lng": 75.7700,
        "rating": 3.9, "reviews": 870, "price": 1600, "class": 2, "free_cancellation": False,
        "address": "Jaisinghpura, Ujjain", "image": None,
        "amenities": ["Free Wi-Fi", "Air conditioning"],
        "breakdown": [("Location", 300, 8), ("Cleanliness", 110, 45), ("Value", 160, 15)],
    },
    {
        "id": "demo-ujn-freeganj", "name": "Freeganj Grand Hotel", "lat": 23.1700, "lng": 75.7960,
        "rating": 4.4, "reviews": 2050, "price": 3600, "class": 4, "free_cancellation": True,
        "address": "Freeganj, Ujjain", "image": None,
        "amenities": ["Free Wi-Fi", "Breakfast", "Restaurant", "Elevator", "Free parking"],
        "breakdown": [("Cleanliness", 420, 20), ("Service", 380, 26), ("Location", 200, 60)],
    },
]

REVIEWS = {
    "demo-ujn-shipra": [
        (5, "2 weeks ago", "A short walk to the temple and Ram Ghat. Clean room and helpful staff for darshan timings."),
        (4, "a month ago", "Good breakfast and quiet rooms. Parking is limited on festival days."),
        (3, "2 months ago", "Location is excellent but the bathroom needed attention."),
    ],
    "demo-ujn-freeganj": [
        (5, "3 weeks ago", "Very clean and comfortable, a little far from the temple but cabs are easy to find."),
        (4, "a month ago", "Great service and food. Traffic near Mahakal can be slow in the morning."),
    ],
}


def _clock(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0").replace(" ", " ")


def transit_payload(arrive_by: datetime, prefer: str | None) -> dict:
    """A Google-Maps-transit-shaped payload (same fields SerpApi returns), generated relative to arrive_by.
    Illustrative service names — no real train numbers."""
    options = []
    if prefer in (None, "train"):
        end = arrive_by - timedelta(minutes=20)
        walk2, train, walk1 = 15, 70, 20
        t_arr = end - timedelta(minutes=walk2)
        t_dep = t_arr - timedelta(minutes=train)
        start = t_dep - timedelta(minutes=walk1)
        options.append({
            "travel_mode": "Transit", "start_time": _clock(start), "end_time": _clock(end), "distance": 58_000,
            "duration": int((end - start).total_seconds()),
            "trips": [
                {"travel_mode": "Walking", "title": "Walk", "duration": walk1 * 60},
                {"travel_mode": "Transit", "title": "Indore – Ujjain Intercity (demo)", "duration": train * 60,
                 "start_stop": {"name": "Indore Junction", "time": _clock(t_dep)},
                 "end_stop": {"name": "Ujjain Junction", "time": _clock(t_arr)},
                 "stops": [{"name": "Dewas Junction"}],
                 "icon": "https://maps.gstatic.com/mapfiles/transit/iw2/svg/rail2.svg",
                 "service_run_by": {"name": "Indian Railways (demo schedule)"}},
                {"travel_mode": "Walking", "title": "Walk", "duration": walk2 * 60},
            ],
        })
    if prefer in (None, "bus"):
        end = arrive_by - timedelta(minutes=35)
        walk2, bus, walk1 = 10, 105, 15
        b_arr = end - timedelta(minutes=walk2)
        b_dep = b_arr - timedelta(minutes=bus)
        start = b_dep - timedelta(minutes=walk1)
        options.append({
            "travel_mode": "Transit", "start_time": _clock(start), "end_time": _clock(end), "distance": 56_000,
            "duration": int((end - start).total_seconds()),
            "trips": [
                {"travel_mode": "Walking", "title": "Walk", "duration": walk1 * 60},
                {"travel_mode": "Transit", "title": "Indore – Ujjain intercity bus (demo)", "duration": bus * 60,
                 "start_stop": {"name": "Sarwate Bus Stand, Indore", "time": _clock(b_dep)},
                 "end_stop": {"name": "Nanakheda Bus Stand, Ujjain", "time": _clock(b_arr)},
                 "stops": [{"name": "Sanwer"}, {"name": "Dharmapuri"}],
                 "icon": "https://maps.gstatic.com/mapfiles/transit/iw2/svg/bus2.svg",
                 "service_run_by": {"name": "Intercity bus operator (demo)"}},
                {"travel_mode": "Walking", "title": "Walk", "duration": walk2 * 60},
            ],
        })
    return {"directions": options}
