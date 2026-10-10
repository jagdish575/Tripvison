"""DEMO MODE dataset — deterministic, labelled, used only when DEMO_MODE=true.

Reproduces the hackathon scenario: Indore (IDR) → Bengaluru (BLR), job interview at Manyata Tech Park.
Airlines are real carriers, but schedules, prices, hotels, reviews and places are illustrative. Hotel,
café and shop names are fictional so no real business is misrepresented. Dates are generated relative to
the mission date the user picks.
"""

from __future__ import annotations

SUPPORTED_ROUTES = {("IDR", "BLR")}

# --------------------------------------------------------------------------- geocoding
PLACES = {
    "manyata tech park": ("Manyata Tech Park", "Nagavara, Bengaluru, Karnataka 560045", 13.0475, 77.6205),
    "manyata": ("Manyata Tech Park", "Nagavara, Bengaluru, Karnataka 560045", 13.0475, 77.6205),
    "electronic city": ("Electronic City", "Electronic City Phase 1, Bengaluru 560100", 12.8452, 77.6602),
    "whitefield": ("Whitefield", "ITPL Main Road, Whitefield, Bengaluru 560066", 12.9857, 77.7365),
    "itpl": ("International Tech Park", "Whitefield, Bengaluru 560066", 12.9857, 77.7365),
    "mg road": ("MG Road", "Mahatma Gandhi Road, Bengaluru 560001", 12.9756, 77.6050),
    "koramangala": ("Koramangala", "Koramangala, Bengaluru 560034", 12.9352, 77.6245),
    "hebbal": ("Hebbal", "Hebbal, Bengaluru 560024", 13.0358, 77.5970),
    "bengaluru city centre": ("Bengaluru city centre", "Bengaluru, Karnataka", 12.9716, 77.5946),
    "bangalore": ("Bengaluru city centre", "Bengaluru, Karnataka", 12.9716, 77.5946),
    "bengaluru": ("Bengaluru city centre", "Bengaluru, Karnataka", 12.9716, 77.5946),
}

# --------------------------------------------------------------------------- flights
# Daily schedule: every flight operates every day.
# (airline, [(flight_no, from, to, dep "HH:MM", arr "HH:MM", arrival day offset)], price per adult, often_delayed)
FLIGHTS = [
    ("IndiGo", [("6E 6312", "IDR", "BLR", "05:35", "07:45", 0)], 5480, False),
    ("Air India Express", [("IX 1124", "IDR", "BLR", "06:40", "08:40", 0)], 4690, False),
    ("IndiGo", [("6E 517", "IDR", "HYD", "05:10", "06:30", 0), ("6E 902", "HYD", "BLR", "07:25", "08:35", 0)], 3890, False),
    ("Akasa Air", [("QP 1381", "IDR", "BLR", "06:05", "08:10", 0)], 6250, True),
    ("Air India", [("AI 2811", "IDR", "BLR", "04:20", "06:25", 0)], 7400, False),
    ("IndiGo", [("6E 6187", "IDR", "BLR", "11:30", "13:35", 0)], 4120, False),
    ("Akasa Air", [("QP 1384", "IDR", "BLR", "13:10", "15:15", 0)], 3980, False),
    ("IndiGo", [("6E 7128", "IDR", "BOM", "16:00", "17:20", 0), ("6E 5310", "BOM", "BLR", "18:30", "20:15", 0)], 3650, False),
    ("IndiGo", [("6E 6311", "IDR", "BLR", "18:40", "20:50", 0)], 4350, False),
    ("Air India", [("AI 2815", "IDR", "BLR", "20:15", "22:25", 0)], 5120, False),
]

AIRPORT_NAMES = {
    "IDR": "Devi Ahilya Bai Holkar Airport",
    "BLR": "Kempegowda International Airport Bengaluru",
    "HYD": "Rajiv Gandhi International Airport",
    "BOM": "Chhatrapati Shivaji Maharaj International Airport",
}

# --------------------------------------------------------------------------- hotels
HOTELS = [
    {
        "id": "demo-lakeview", "name": "Lakeview Residency Hebbal", "lat": 13.0410, "lng": 77.6115,
        "rating": 4.3, "reviews": 2180, "price": 3400, "class": 4, "free_cancellation": True,
        "address": "Outer Ring Road, Nagavara, Bengaluru",
        "amenities": ["Free Wi-Fi", "Breakfast", "Air conditioning", "Airport shuttle", "Fitness centre", "Restaurant"],
        "image": None,
        "breakdown": [("Location", 412, 18), ("Cleanliness", 280, 41), ("Service", 305, 22), ("Breakfast", 150, 31),
                      ("Noise", 22, 37)],
    },
    {
        "id": "demo-manyata", "name": "Manyata Business Hotel", "lat": 13.0502, "lng": 77.6230,
        "rating": 4.0, "reviews": 860, "price": 4600, "class": 4, "free_cancellation": False,
        "address": "Manyata Tech Park Road, Nagavara, Bengaluru",
        "amenities": ["Free Wi-Fi", "Business centre", "Air conditioning", "Restaurant", "Room service"],
        "image": None,
        "breakdown": [("Location", 210, 6), ("Cleanliness", 120, 30), ("Service", 140, 26), ("Noise", 10, 25)],
    },
    {
        "id": "demo-nagawara", "name": "Nagawara Comfort Inn", "lat": 13.0290, "lng": 77.6360,
        "rating": 3.8, "reviews": 1240, "price": 2150, "class": 3, "free_cancellation": True,
        "address": "Thanisandra Main Road, Bengaluru",
        "amenities": ["Free Wi-Fi", "Air conditioning", "Free parking"],
        "image": None,
        "breakdown": [("Location", 160, 25), ("Cleanliness", 90, 58), ("Value", 140, 20)],
    },
    {
        "id": "demo-yelahanka", "name": "Airport Road Suites Yelahanka", "lat": 13.1000, "lng": 77.5960,
        "rating": 4.4, "reviews": 3050, "price": 2900, "class": 4, "free_cancellation": True,
        "address": "Bellary Road, Yelahanka, Bengaluru",
        "amenities": ["Free Wi-Fi", "Breakfast", "Pool", "Airport shuttle", "Free parking"],
        "image": None,
        "breakdown": [("Location", 300, 120), ("Cleanliness", 420, 30), ("Service", 390, 25), ("Breakfast", 260, 20)],
    },
    {
        "id": "demo-indiranagar", "name": "Indiranagar Boutique Stay", "lat": 12.9719, "lng": 77.6412,
        "rating": 4.6, "reviews": 640, "price": 5800, "class": 4, "free_cancellation": True,
        "address": "100 Feet Road, Indiranagar, Bengaluru",
        "amenities": ["Free Wi-Fi", "Breakfast", "Rooftop bar", "Air conditioning"],
        "image": None,
        "breakdown": [("Cleanliness", 180, 6), ("Service", 170, 9), ("Noise", 15, 28)],
    },
]

REVIEWS = {
    "demo-lakeview": [
        (5, "2 weeks ago", "Stayed here the night before an interview at Manyata. The location is perfect, the tech park gate is a short cab ride away. Room was clean and quiet."),
        (4, "a month ago", "Good breakfast spread and helpful staff at the front desk. Check-in was quick even at 10 pm."),
        (4, "a month ago", "Clean rooms, comfortable bed. Some traffic noise from the Outer Ring Road if your room faces the highway, ask for an inner room."),
        (5, "2 months ago", "Excellent location for Manyata Tech Park. Staff arranged an early cab for me without any fuss."),
        (3, "2 months ago", "Breakfast was average and the restaurant was crowded. Wi-Fi was good though."),
        (4, "3 months ago", "Convenient for the airport and the tech park. Spotless bathroom."),
        (2, "3 months ago", "Room facing the road was noisy at night with constant honking. Staff did move me the next day."),
        (5, "4 months ago", "Friendly staff, clean room, great value for Bengaluru prices."),
    ],
    "demo-manyata": [
        (4, "3 weeks ago", "Walking distance to Manyata Tech Park, which is the main reason to stay here."),
        (2, "a month ago", "Check-in took almost 40 minutes, the front desk was slow and understaffed."),
        (3, "2 months ago", "Rooms are okay but the bathroom was not clean when we arrived."),
        (4, "2 months ago", "Convenient location and good room service. A bit pricey for what you get."),
        (2, "3 months ago", "Noisy at night because of construction next door."),
        (5, "4 months ago", "Helpful staff and a quiet business centre to prepare for meetings."),
    ],
    "demo-yelahanka": [
        (5, "a week ago", "Very clean, great breakfast buffet and the airport shuttle is a big plus."),
        (4, "a month ago", "Lovely pool and friendly staff. Location is far from the city centre though."),
        (3, "2 months ago", "Good hotel but it took over an hour to reach Whitefield in the morning traffic."),
        (5, "3 months ago", "Spotless rooms and excellent service. Perfect for an early flight."),
    ],
    "demo-nagawara": [
        (4, "a month ago", "Affordable and close to the tech park. Basic but comfortable."),
        (2, "2 months ago", "Room smelled damp and the bedsheets had stains. Not clean."),
        (3, "3 months ago", "Good value, staff were helpful, but the Wi-Fi kept dropping."),
    ],
}

# --------------------------------------------------------------------------- local places
# category slug -> [(name, dlat, dlng, rating, reviews, type, hours)]
LOCAL = {
    "cafe": [
        ("Filter Kaapi House", 0.0021, -0.0018, 4.5, 1840, "Coffee shop", "Open · Closes 10 pm"),
        ("Brew Theory Café", -0.0040, 0.0025, 4.3, 960, "Café", "Open · Closes 11 pm"),
        ("Lakeside Coffee Roasters", -0.0080, -0.0090, 4.6, 2210, "Coffee roasters", "Opens 7 am"),
        ("Tech Park Food Court Café", 0.0006, 0.0010, 4.0, 3120, "Café", "Open 24 hours"),
    ],
    "pharmacy": [
        ("CarePoint Pharmacy", 0.0035, 0.0012, 4.4, 410, "Pharmacy", "Open 24 hours"),
        ("Nagavara Medicals", -0.0052, 0.0061, 4.2, 230, "Pharmacy", "Open · Closes 11 pm"),
        ("WellLife Chemists", -0.0110, -0.0040, 4.5, 690, "Pharmacy", "Opens 8 am"),
    ],
    "restaurant": [
        ("Udupi Breakfast House", 0.0028, -0.0031, 4.4, 5200, "South Indian restaurant", "Opens 6:30 am"),
        ("Darshini Express", -0.0019, 0.0044, 4.2, 2800, "Vegetarian restaurant", "Opens 6 am"),
        ("Hebbal Kitchen & Co.", -0.0090, -0.0070, 4.3, 1330, "Restaurant", "Opens 8 am"),
    ],
    "stationery": [
        ("Campus Stationers", 0.0030, 0.0020, 4.3, 190, "Stationery store", "Opens 9 am"),
        ("PrintHub Xerox & Stationery", -0.0040, -0.0010, 4.1, 260, "Print shop", "Opens 8 am"),
    ],
    "coworking": [
        ("Northside Coworking", 0.0050, -0.0030, 4.6, 380, "Coworking space", "Opens 8 am"),
        ("DeskPoint Manyata", 0.0012, 0.0024, 4.4, 210, "Coworking space", "Open 24 hours"),
    ],
    "atm": [("ATM — Outer Ring Road", 0.0010, 0.0015, 3.9, 40, "ATM", "Open 24 hours")],
    "salon": [("Groom Studio", 0.0040, 0.0030, 4.5, 520, "Salon", "Opens 9 am")],
    "gift": [("The Gift Box", -0.0030, 0.0020, 4.4, 150, "Gift shop", "Opens 10 am")],
    "attraction": [("Hebbal Lake Walkway", -0.0120, -0.0230, 4.4, 3900, "Lake", "Open · Closes 6 pm")],
    "viewpoint": [("Nagavara Lake Promenade", -0.0080, 0.0060, 4.3, 1500, "Viewpoint", "Open · Closes 7 pm")],
    "park": [("Rachenahalli Lake Park", 0.0200, 0.0150, 4.4, 2100, "Park", "Opens 6 am")],
}
