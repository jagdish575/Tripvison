"""Static city reference data: city-centre coordinates for Indian cities and towns.

This is stable public geography (not travel inventory). It lets TripMission resolve places that have
no airport — Ujjain, Mathura, Haridwar — without spending a live search, and gives airport cities a
real city-centre point (Bengaluru's airport is ~35 km from the city). Anything not listed here is
resolved with a live geocoding lookup.
"""

from __future__ import annotations

# city, country, lat, lng, aliases
_CITIES: list[tuple[str, str, float, float, tuple[str, ...]]] = [
    # --- airport cities: city-centre points
    ("Bengaluru", "IN", 12.9716, 77.5946, ("bangalore",)),
    ("Indore", "IN", 22.7196, 75.8577, ()),
    ("Delhi", "IN", 28.6139, 77.2090, ("new delhi",)),
    ("Mumbai", "IN", 19.0760, 72.8777, ("bombay",)),
    ("Chennai", "IN", 13.0827, 80.2707, ("madras",)),
    ("Hyderabad", "IN", 17.3850, 78.4867, ()),
    ("Kolkata", "IN", 22.5726, 88.3639, ("calcutta",)),
    ("Pune", "IN", 18.5204, 73.8567, ("poona",)),
    ("Ahmedabad", "IN", 23.0225, 72.5714, ()),
    ("Jaipur", "IN", 26.9124, 75.7873, ()),
    ("Lucknow", "IN", 26.8467, 80.9462, ()),
    ("Bhopal", "IN", 23.2599, 77.4126, ()),
    ("Kochi", "IN", 9.9312, 76.2673, ("cochin", "ernakulam")),
    ("Chandigarh", "IN", 30.7333, 76.7794, ()),
    ("Nagpur", "IN", 21.1458, 79.0882, ()),
    ("Varanasi", "IN", 25.3176, 82.9739, ("banaras", "benares")),
    ("Patna", "IN", 25.5941, 85.1376, ()),
    ("Guwahati", "IN", 26.1445, 91.7362, ()),
    ("Bhubaneswar", "IN", 20.2961, 85.8245, ()),
    ("Coimbatore", "IN", 11.0168, 76.9558, ()),
    ("Udaipur", "IN", 24.5854, 73.7125, ()),
    ("Thiruvananthapuram", "IN", 8.5241, 76.9366, ("trivandrum",)),
    ("Agra", "IN", 27.1767, 78.0081, ()),
    ("Mysuru", "IN", 12.2958, 76.6394, ("mysore",)),
    ("Nashik", "IN", 19.9975, 73.7898, ("nasik",)),
    ("Gwalior", "IN", 26.2183, 78.1828, ()),
    ("Jabalpur", "IN", 23.1815, 79.9864, ()),
    ("Surat", "IN", 21.1702, 72.8311, ()),
    ("Vadodara", "IN", 22.3072, 73.1812, ("baroda",)),
    ("Raipur", "IN", 21.2514, 81.6296, ()),
    ("Madurai", "IN", 9.9252, 78.1198, ()),
    ("Visakhapatnam", "IN", 17.6868, 83.2185, ("vizag",)),
    ("Jodhpur", "IN", 26.2389, 73.0243, ()),
    ("Amritsar", "IN", 31.6340, 74.8723, ()),
    ("Dehradun", "IN", 30.3165, 78.0322, ()),
    ("Kanpur", "IN", 26.4499, 80.3319, ()),
    ("Prayagraj", "IN", 25.4358, 81.8463, ("allahabad",)),
    # --- cities and towns without a commercial airport
    ("Ujjain", "IN", 23.1793, 75.7849, ()),
    ("Dewas", "IN", 22.9676, 76.0534, ()),
    ("Omkareshwar", "IN", 22.2457, 76.1518, ()),
    ("Maheshwar", "IN", 22.1769, 75.5878, ()),
    ("Mandu", "IN", 22.3667, 75.3833, ("mandav",)),
    ("Mhow", "IN", 22.5524, 75.7565, ("dr. ambedkar nagar",)),
    ("Ratlam", "IN", 23.3315, 75.0367, ()),
    ("Sagar", "IN", 23.8388, 78.7378, ()),
    ("Satna", "IN", 24.6005, 80.8322, ()),
    ("Mathura", "IN", 27.4924, 77.6737, ()),
    ("Vrindavan", "IN", 27.5650, 77.6593, ()),
    ("Haridwar", "IN", 29.9457, 78.1642, ()),
    ("Rishikesh", "IN", 30.0869, 78.2676, ()),
    ("Nainital", "IN", 29.3803, 79.4636, ()),
    ("Kota", "IN", 25.2138, 75.8648, ()),
    ("Ajmer", "IN", 26.4499, 74.6399, ()),
    ("Pushkar", "IN", 26.4897, 74.5511, ()),
    ("Chittorgarh", "IN", 24.8887, 74.6269, ()),
    ("Mount Abu", "IN", 24.5926, 72.7156, ()),
    ("Katra", "IN", 32.9916, 74.9318, ("vaishno devi",)),
    ("Lonavala", "IN", 18.7546, 73.4062, ()),
    ("Mahabaleshwar", "IN", 17.9307, 73.6477, ()),
    ("Solapur", "IN", 17.6599, 75.9064, ()),
    ("Ahmednagar", "IN", 19.0948, 74.7480, ()),
    ("Satara", "IN", 17.6805, 74.0183, ()),
    ("Puri", "IN", 19.8135, 85.8312, ()),
    ("Cuttack", "IN", 20.4625, 85.8830, ()),
    ("Bodh Gaya", "IN", 24.6961, 84.9870, ()),
    ("Jamshedpur", "IN", 22.8046, 86.2029, ()),
    ("Dhanbad", "IN", 23.7957, 86.4304, ()),
    ("Durgapur", "IN", 23.5204, 87.3119, ()),
    ("Asansol", "IN", 23.6739, 86.9524, ()),
    ("Bilaspur", "IN", 22.0797, 82.1409, ()),
    ("Jhansi", "IN", 25.4484, 78.5685, ()),
    ("Aligarh", "IN", 27.8974, 78.0880, ()),
    ("Meerut", "IN", 28.9845, 77.7064, ()),
    ("Bareilly", "IN", 28.3670, 79.4304, ()),
    ("Ooty", "IN", 11.4102, 76.6950, ("udhagamandalam",)),
    ("Kodaikanal", "IN", 10.2381, 77.4892, ()),
    ("Munnar", "IN", 10.0889, 77.0595, ()),
    ("Alappuzha", "IN", 9.4981, 76.3388, ("alleppey",)),
    ("Thrissur", "IN", 10.5276, 76.2144, ()),
    ("Kanyakumari", "IN", 8.0883, 77.5385, ()),
    ("Tirunelveli", "IN", 8.7139, 77.7567, ()),
    ("Salem", "IN", 11.6643, 78.1460, ()),
    ("Vellore", "IN", 12.9165, 79.1325, ()),
    ("Mahabalipuram", "IN", 12.6208, 80.1945, ("mamallapuram",)),
    ("Hosur", "IN", 12.7409, 77.8253, ()),
    ("Udupi", "IN", 13.3409, 74.7421, ()),
    ("Hampi", "IN", 15.3350, 76.4600, ()),
    ("Nellore", "IN", 14.4426, 79.9865, ()),
    ("Warangal", "IN", 17.9689, 79.5941, ()),
    ("Guntur", "IN", 16.3067, 80.4365, ()),
    ("Manali", "IN", 32.2432, 77.1892, ()),
    ("Gangtok", "IN", 27.3389, 88.6065, ()),
    ("Shillong", "IN", 25.5788, 91.8933, ()),
]

CITY_CENTRES: dict[str, tuple[str, str, float, float]] = {}
for _city, _country, _lat, _lng, _aliases in _CITIES:
    for _key in (_city, *_aliases):
        CITY_CENTRES.setdefault(_key.casefold(), (_city, _country, _lat, _lng))


def lookup_city(name: str) -> tuple[str, str, float, float] | None:
    """'Ujjain' / 'ujjain, MP' / 'Ujjain, India' -> (city, country, lat, lng)."""
    key = name.strip().split(",")[0].strip().casefold()
    return CITY_CENTRES.get(key)
