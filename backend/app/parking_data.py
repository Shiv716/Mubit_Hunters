"""Public parking facts from an attributed OSM snapshot; no inferred availability."""
from __future__ import annotations

import math
from urllib.parse import urlsplit

# Greater London and its immediate edges. This is coverage, not a jurisdiction boundary.
BOUNDS = (-0.51, 51.28, 0.34, 51.70)


def in_coverage(lat: float, lon: float) -> bool:
    west, south, east, north = BOUNDS
    return math.isfinite(lat) and math.isfinite(lon) and south <= lat <= north and west <= lon <= east


def distance_m(lat: float, lon: float, other_lat: float, other_lon: float) -> int:
    a, b = math.radians(lat), math.radians(other_lat)
    dlat, dlon = b - a, math.radians(other_lon - lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return round(6371000 * 2 * math.asin(min(1, math.sqrt(h))))


def safe_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password else None
    except ValueError:
        return None


def normalise(element: dict) -> dict | None:
    tags = element.get("tags", {})
    access = tags.get("access", "").lower()
    vehicle_access = [tags.get(key, "").lower() for key in ("vehicle", "motor_vehicle", "motorcar")]
    if tags.get("amenity") != "parking" or any(value in ("no", "private", "residents", "permit") for value in vehicle_access):
        return None
    if tags.get("tourist_bus") == "designated" or tags.get("bus") == "designated" or tags.get("hgv") == "designated":
        return None
    if tags.get("disused") == "yes" or tags.get("abandoned") == "yes":
        return None
    if "customers" in vehicle_access:
        access = "customers"
    # A named place is not enough to overrule restricted access.
    if access not in ("", "yes", "public", "permissive", "customers"):
        return None
    if tags.get("parking") == "carports" or tags.get("parking:condition") in ("residents", "private"):
        return None
    name = tags.get("name") or tags.get("name:en")
    if not name and access == "" and tags.get("fee") != "yes":
        return None  # Do not suggest anonymous, possibly private parking areas.
    coordinates = element.get("center", element)
    lat, lon = coordinates.get("lat"), coordinates.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not in_coverage(lat, lon):
        return None
    kind = element.get("type")
    if kind not in ("node", "way", "relation") or not isinstance(element.get("id"), int):
        return None
    def text(key):
        value = tags.get(key)
        return str(value)[:250] if value else None
    street = " ".join(filter(None, [text("addr:housenumber"), text("addr:street")]))
    address = ", ".join(filter(None, [street, text("addr:suburb"), text("addr:postcode")]))
    return {
        "id": f"{kind}/{element['id']}", "lat": lat, "lon": lon,
        "name": (name or text("operator") or (f"Parking · {street}" if street else "Mapped car park"))[:150],
        "address": address or None, "operator": text("operator"),
        "type": tags.get("parking", "surface"),
        "covered": tags.get("covered") == "yes" or tags.get("parking") in ("underground", "multi-storey"),
        "access": "customers" if access == "customers" else "public" if access in ("yes", "public", "permissive") else "unknown",
        "fee": tags.get("fee") if tags.get("fee") in ("yes", "no") else "unknown",
        "charge": text("charge"), "fee_condition": text("fee:conditional"),
        "access_condition": text("motorcar:conditional") or text("motor_vehicle:conditional") or text("access:conditional"),
        "reservation": text("reservation"),
        "hours": text("opening_hours"), "maxstay": text("maxstay"),
        "capacity": text("capacity"), "disabled_bays": text("capacity:disabled"),
        "wheelchair": text("wheelchair"), "height_limit": text("maxheight"),
        "website": safe_url(tags.get("website") or tags.get("contact:website")),
        "source_url": f"https://www.openstreetmap.org/{kind}/{element['id']}",
        "availability": "unknown",
    }
