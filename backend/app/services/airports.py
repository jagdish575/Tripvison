"""Static airport reference data (IATA codes + coordinates) and a city/code resolver.

Google Flights needs IATA codes, and the itinerary engine needs airport coordinates for ground
transfers. This is stable public reference data, not travel inventory.
"""

from __future__ import annotations

import re

from app.schemas.travel import Airport, GeoPoint

# code, city, airport name, country, lat, lng, aliases
_AIRPORTS: list[tuple[str, str, str, str, float, float, tuple[str, ...]]] = [
    ("IDR", "Indore", "Devi Ahilya Bai Holkar Airport", "IN", 22.7218, 75.8011, ()),
    ("BLR", "Bengaluru", "Kempegowda International Airport", "IN", 13.1986, 77.7066, ("bangalore", "bengaluru")),
    ("DEL", "Delhi", "Indira Gandhi International Airport", "IN", 28.5562, 77.1000, ("new delhi", "ncr", "gurgaon", "gurugram", "noida")),
    ("BOM", "Mumbai", "Chhatrapati Shivaji Maharaj International Airport", "IN", 19.0896, 72.8656, ("bombay", "navi mumbai", "thane")),
    ("MAA", "Chennai", "Chennai International Airport", "IN", 12.9941, 80.1709, ("madras",)),
    ("HYD", "Hyderabad", "Rajiv Gandhi International Airport", "IN", 17.2403, 78.4294, ("secunderabad",)),
    ("CCU", "Kolkata", "Netaji Subhas Chandra Bose International Airport", "IN", 22.6547, 88.4467, ("calcutta",)),
    ("PNQ", "Pune", "Pune Airport", "IN", 18.5821, 73.9197, ("poona",)),
    ("AMD", "Ahmedabad", "Sardar Vallabhbhai Patel International Airport", "IN", 23.0772, 72.6347, ("gandhinagar",)),
    ("GOI", "Goa", "Dabolim Airport", "IN", 15.3808, 73.8314, ("panaji", "vasco da gama", "margao")),
    ("GOX", "North Goa", "Manohar International Airport (Mopa)", "IN", 15.7444, 73.8606, ("mopa",)),
    ("COK", "Kochi", "Cochin International Airport", "IN", 10.1520, 76.4019, ("cochin", "ernakulam")),
    ("TRV", "Thiruvananthapuram", "Trivandrum International Airport", "IN", 8.4821, 76.9201, ("trivandrum",)),
    ("JAI", "Jaipur", "Jaipur International Airport", "IN", 26.8242, 75.8122, ()),
    ("LKO", "Lucknow", "Chaudhary Charan Singh International Airport", "IN", 26.7606, 80.8893, ()),
    ("BHO", "Bhopal", "Raja Bhoj Airport", "IN", 23.2875, 77.3374, ()),
    ("NAG", "Nagpur", "Dr. Babasaheb Ambedkar International Airport", "IN", 21.0922, 79.0472, ()),
    ("PAT", "Patna", "Jay Prakash Narayan Airport", "IN", 25.5913, 85.0880, ()),
    ("GAU", "Guwahati", "Lokpriya Gopinath Bordoloi International Airport", "IN", 26.1061, 91.5859, ()),
    ("BBI", "Bhubaneswar", "Biju Patnaik International Airport", "IN", 20.2444, 85.8178, ()),
    ("IXC", "Chandigarh", "Chandigarh International Airport", "IN", 30.6735, 76.7885, ("mohali", "panchkula")),
    ("SXR", "Srinagar", "Srinagar International Airport", "IN", 33.9871, 74.7742, ()),
    ("ATQ", "Amritsar", "Sri Guru Ram Dass Jee International Airport", "IN", 31.7096, 74.7973, ()),
    ("VNS", "Varanasi", "Lal Bahadur Shastri International Airport", "IN", 25.4524, 82.8593, ("banaras", "benares")),
    ("IXB", "Siliguri", "Bagdogra Airport", "IN", 26.6812, 88.3286, ("bagdogra", "darjeeling")),
    ("CJB", "Coimbatore", "Coimbatore International Airport", "IN", 11.0300, 77.0434, ()),
    ("IXM", "Madurai", "Madurai Airport", "IN", 9.8345, 78.0934, ()),
    ("IXE", "Mangaluru", "Mangaluru International Airport", "IN", 12.9613, 74.8901, ("mangalore",)),
    ("VTZ", "Visakhapatnam", "Visakhapatnam Airport", "IN", 17.7212, 83.2245, ("vizag",)),
    ("RPR", "Raipur", "Swami Vivekananda Airport", "IN", 21.1804, 81.7388, ()),
    ("IXR", "Ranchi", "Birsa Munda Airport", "IN", 23.3143, 85.3217, ()),
    ("UDR", "Udaipur", "Maharana Pratap Airport", "IN", 24.6177, 73.8961, ()),
    ("JDH", "Jodhpur", "Jodhpur Airport", "IN", 26.2511, 73.0489, ()),
    ("STV", "Surat", "Surat Airport", "IN", 21.1141, 72.7418, ()),
    ("BDQ", "Vadodara", "Vadodara Airport", "IN", 22.3362, 73.2263, ("baroda",)),
    ("IXZ", "Port Blair", "Veer Savarkar International Airport", "IN", 11.6412, 92.7297, ("andaman",)),
    ("DED", "Dehradun", "Jolly Grant Airport", "IN", 30.1897, 78.1803, ("rishikesh", "mussoorie")),
    ("IXJ", "Jammu", "Jammu Airport", "IN", 32.6891, 74.8374, ()),
    ("TRZ", "Tiruchirappalli", "Tiruchirappalli International Airport", "IN", 10.7654, 78.7097, ("trichy",)),
    ("VGA", "Vijayawada", "Vijayawada International Airport", "IN", 16.5304, 80.7968, ()),
    ("IXL", "Leh", "Kushok Bakula Rimpochee Airport", "IN", 34.1359, 77.5465, ("ladakh",)),
    ("GWL", "Gwalior", "Rajmata Vijaya Raje Scindia Airport", "IN", 26.2933, 78.2278, ()),
    ("JLR", "Jabalpur", "Jabalpur Airport", "IN", 23.1778, 80.0520, ()),
    ("IXA", "Agartala", "Maharaja Bir Bikram Airport", "IN", 23.8870, 91.2404, ()),
    ("IMF", "Imphal", "Imphal International Airport", "IN", 24.7600, 93.8967, ()),
    ("HBX", "Hubballi", "Hubballi Airport", "IN", 15.3617, 75.0849, ("hubli", "dharwad")),
    ("KNU", "Kanpur", "Kanpur Airport", "IN", 26.4044, 80.4101, ()),
    ("IXU", "Aurangabad", "Aurangabad Airport", "IN", 19.8627, 75.3981, ("chhatrapati sambhajinagar",)),
    ("AGR", "Agra", "Agra Airport", "IN", 27.1558, 77.9609, ()),
    ("IXD", "Prayagraj", "Prayagraj Airport", "IN", 25.4401, 81.7340, ("allahabad",)),
    ("GAY", "Gaya", "Gaya Airport", "IN", 24.7443, 84.9512, ()),
    ("TIR", "Tirupati", "Tirupati Airport", "IN", 13.6325, 79.5433, ()),
    ("MYQ", "Mysuru", "Mysore Airport", "IN", 12.2300, 76.6558, ("mysore",)),
    ("IXG", "Belagavi", "Belagavi Airport", "IN", 15.8593, 74.6183, ("belgaum",)),
    ("SAG", "Shirdi", "Shirdi Airport", "IN", 19.6886, 74.3789, ()),
    ("ISK", "Nashik", "Nashik Airport (Ozar)", "IN", 20.1191, 73.9129, ("nasik",)),
    ("KQH", "Kishangarh", "Kishangarh Airport", "IN", 26.6015, 74.8142, ()),
    ("GOP", "Gorakhpur", "Gorakhpur Airport", "IN", 26.7397, 83.4497, ()),
    ("DIB", "Dibrugarh", "Dibrugarh Airport", "IN", 27.4839, 95.0169, ()),
    ("KLH", "Kolhapur", "Kolhapur Airport", "IN", 16.6647, 74.2894, ()),
    ("JSA", "Jaisalmer", "Jaisalmer Airport", "IN", 26.8887, 70.8650, ()),
    ("BKB", "Bikaner", "Nal Airport", "IN", 28.0706, 73.2072, ()),
    ("PNY", "Puducherry", "Puducherry Airport", "IN", 11.9680, 79.8120, ("pondicherry", "pondy")),
    ("TCR", "Thoothukudi", "Tuticorin Airport", "IN", 8.7242, 78.0258, ("tuticorin",)),
    ("RJA", "Rajahmundry", "Rajahmundry Airport", "IN", 17.1104, 81.8182, ("rajamahendravaram",)),
    ("DHM", "Dharamshala", "Kangra Airport (Gaggal)", "IN", 32.1651, 76.2634, ("dharamsala", "mcleodganj")),
    ("KUU", "Kullu", "Bhuntar Airport", "IN", 31.8767, 77.1544, ()),
    ("SLV", "Shimla", "Shimla Airport", "IN", 31.0818, 77.0680, ()),
    ("PGH", "Pantnagar", "Pantnagar Airport", "IN", 29.0334, 79.4737, ()),
    ("BHJ", "Bhuj", "Bhuj Airport", "IN", 23.2878, 69.6702, ()),
    ("HJR", "Khajuraho", "Khajuraho Airport", "IN", 24.8172, 79.9186, ()),
    ("CCJ", "Kozhikode", "Calicut International Airport", "IN", 11.1368, 75.9553, ("calicut",)),
    ("CNN", "Kannur", "Kannur International Airport", "IN", 11.9186, 75.5472, ()),
    ("DXB", "Dubai", "Dubai International Airport", "AE", 25.2532, 55.3657, ()),
    ("AUH", "Abu Dhabi", "Zayed International Airport", "AE", 24.4330, 54.6511, ()),
    ("DOH", "Doha", "Hamad International Airport", "QA", 25.2731, 51.6081, ()),
    ("SIN", "Singapore", "Singapore Changi Airport", "SG", 1.3644, 103.9915, ()),
    ("KUL", "Kuala Lumpur", "Kuala Lumpur International Airport", "MY", 2.7456, 101.7099, ()),
    ("BKK", "Bangkok", "Suvarnabhumi Airport", "TH", 13.6900, 100.7501, ()),
    ("CMB", "Colombo", "Bandaranaike International Airport", "LK", 7.1808, 79.8841, ()),
    ("KTM", "Kathmandu", "Tribhuvan International Airport", "NP", 27.6966, 85.3591, ()),
    ("LHR", "London", "Heathrow Airport", "GB", 51.4700, -0.4543, ()),
    ("FRA", "Frankfurt", "Frankfurt Airport", "DE", 50.0379, 8.5622, ()),
    ("CDG", "Paris", "Charles de Gaulle Airport", "FR", 49.0097, 2.5479, ()),
    ("JFK", "New York", "John F. Kennedy International Airport", "US", 40.6413, -73.7781, ("nyc",)),
    ("SFO", "San Francisco", "San Francisco International Airport", "US", 37.6213, -122.3790, ("bay area",)),
]

AIRPORTS: dict[str, Airport] = {}
_ALIASES: dict[str, str] = {}

for code, city, name, country, lat, lng, aliases in _AIRPORTS:
    AIRPORTS[code] = Airport(code=code, city=city, name=name, country=country, location=GeoPoint(lat=lat, lng=lng))
    for key in (city, *aliases):
        _ALIASES.setdefault(key.casefold(), code)


_CODE_IN_PARENS = re.compile(r"\(([A-Za-z]{3})\)")


def _clean(query: str) -> str:
    """'Bangalore (BLR)' -> 'BLR'; 'BLR - Bengaluru' -> 'BLR'; 'Indore, India' -> 'Indore'."""
    text = query.strip()
    match = _CODE_IN_PARENS.search(text)
    if match and match.group(1).upper() in AIRPORTS:
        return match.group(1).upper()
    head = text.split(" - ")[0].split(",")[0].strip()
    return head or text


def resolve_airport(query: str) -> Airport | None:
    text = _clean(query)
    if len(text) == 3 and text.upper() in AIRPORTS:
        return AIRPORTS[text.upper()]
    code = _ALIASES.get(text.casefold())
    return AIRPORTS[code] if code else None


def airports_within(point: GeoPoint, radius_km: float) -> list[tuple[Airport, float]]:
    """Airports within `radius_km` of a point, nearest first (straight-line km)."""
    from app.services.geo import haversine_km

    found = [(a, haversine_km(point, a.location)) for a in AIRPORTS.values()]
    return sorted([(a, d) for a, d in found if d <= radius_km], key=lambda x: x[1])


def search_airports(query: str, limit: int = 8) -> list[Airport]:
    q = query.strip().casefold()
    if not q:
        return []
    exact = resolve_airport(query)
    seen: set[str] = set()
    results: list[Airport] = []
    if exact:
        results.append(exact)
        seen.add(exact.code)
    for alias, code in _ALIASES.items():
        if code in seen:
            continue
        if alias.startswith(q) or (len(q) >= 3 and q in alias):
            results.append(AIRPORTS[code])
            seen.add(code)
    for code, airport in AIRPORTS.items():
        if code not in seen and code.casefold().startswith(q):
            results.append(airport)
            seen.add(code)
    return results[:limit]
