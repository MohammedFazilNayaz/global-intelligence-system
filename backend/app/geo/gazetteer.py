"""
Canonical Gazetteer and Spatial Reference Catalog for Geographic Normalization.
Provides verified municipal center coordinates and canonical maritime zones.
STRICT INVARIANT: No synthetic coordinates, no random jittering.
"""

from typing import Optional, Dict, Tuple, Set


# Verified Municipal Hubs: Coordinates of official municipal centers [latitude, longitude]
# Classification: LocationState.APPROXIMATE, CoordinatePrecision.MUNICIPAL_CENTROID
VERIFIED_MUNICIPAL_CENTROIDS: Dict[str, Tuple[float, float, str, str]] = {
    # Key: normalized_name -> (latitude, longitude, country_code, canonical_name)
    "washington": (38.9072, -77.0369, "US", "Washington D.C."),
    "washington dc": (38.9072, -77.0369, "US", "Washington D.C."),
    "washington post": (38.9072, -77.0369, "US", "Washington D.C."),
    "new york": (40.7128, -74.0060, "US", "New York City"),
    "new york city": (40.7128, -74.0060, "US", "New York City"),
    "london": (51.5074, -0.1278, "GB", "London"),
    "frankfurt": (50.1109, 8.6821, "DE", "Frankfurt"),
    "tokyo": (35.6895, 139.6917, "JP", "Tokyo"),
    "beijing": (39.9042, 116.4074, "CN", "Beijing"),
    "moscow": (55.7558, 37.6173, "RU", "Moscow"),
    "kyiv": (50.4501, 30.5234, "UA", "Kyiv"),
    "paris": (48.8566, 2.3522, "FR", "Paris"),
    "berlin": (52.5200, 13.4050, "DE", "Berlin"),
    "brussels": (50.8503, 4.3517, "BE", "Brussels"),
    "geneva": (46.2044, 6.1432, "CH", "Geneva"),
    "singapore": (1.3521, 103.8198, "SG", "Singapore"),
    "taipei": (25.0330, 121.5654, "TW", "Taipei"),
    "sydney": (-33.8688, 151.2093, "AU", "Sydney"),
    "new delhi": (28.6139, 77.2090, "IN", "New Delhi"),
    "riyadh": (24.7136, 46.6753, "SA", "Riyadh"),
    "tehran": (35.6892, 51.3890, "IR", "Tehran"),
    "cairo": (30.0444, 31.2357, "EG", "Cairo"),
    "brasilia": (-15.7975, -47.8919, "BR", "Brasilia"),
    "ottawa": (45.4215, -75.6972, "CA", "Ottawa"),
    "johannesburg": (-26.2041, 28.0473, "ZA", "Johannesburg"),
    "ternate": (0.7893, 127.3610, "ID", "Ternate"),
    "ruteng": (-8.6131, 120.4721, "ID", "Ruteng"),
    "puerto chacabuco": (-45.4667, -72.8167, "CL", "Puerto Chacabuco"),
    "santiago": (-33.4489, -70.6693, "CL", "Santiago"),
}


# Canonical Maritime Zones & Strategic Waterways
# STRICT INVARIANT: Do not invent point coordinates for maritime regions.
# These remain REGIONAL until authoritative sensor coordinates (e.g. AIS vessel alert) exist.
CANONICAL_MARITIME_ZONES: Set[str] = {
    "red sea",
    "persian gulf",
    "gulf of oman",
    "bab el mandeb",
    "bab el-mandeb",
    "strait of malacca",
    "gulf of aden",
    "taiwan strait",
    "south china sea",
    "east china sea",
    "black sea",
    "baltic sea",
    "mediterranean sea",
    "mediterranean",
    "arabian sea",
    "sea of japan",
    "north sea",
    "suez canal",
    "panama canal",
    "strait of hormuz",
}


def lookup_municipal_centroid(name: str) -> Optional[Tuple[float, float, str, str]]:
    """Lookup authentic municipal coordinates by normalized name."""
    if not name:
        return None
    key = name.strip().lower().replace(".", "")
    return VERIFIED_MUNICIPAL_CENTROIDS.get(key)


def is_maritime_zone(name: str) -> bool:
    """Check if location string references a recognized maritime zone or international waterway."""
    if not name:
        return False
    key = name.strip().lower().replace(".", "").replace("-", " ")
    if key in CANONICAL_MARITIME_ZONES:
        return True
    for zone in CANONICAL_MARITIME_ZONES:
        if zone in key:
            return True
    return False
