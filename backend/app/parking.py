"""Public, read-only map endpoints. No case or account data is exposed."""
from __future__ import annotations

import json
import os
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from .parking_data import BOUNDS, distance_m, in_coverage

router = APIRouter(prefix="/api/parking", tags=["parking"])
DATA = Path(__file__).resolve().parent.parent / "data" / "parking-london.json"
_search_cache: OrderedDict = OrderedDict()
_search_lock = threading.Lock()
_last_search = 0.0


@lru_cache(maxsize=1)
def snapshot():
    return json.loads(DATA.read_text(encoding="utf-8"))


@router.get("/nearby")
def nearby(lat: float = Query(51.5136, ge=-90, le=90), lon: float = Query(-0.1365, ge=-180, le=180),
           radius: int = Query(2500, ge=300, le=6000)):
    if not in_coverage(lat, lon):
        raise HTTPException(422, "Parking coverage currently includes London. Search a London destination or move the map back to London.")
    data = snapshot()
    places = []
    for place in data["places"]:
        distance = distance_m(lat, lon, place["lat"], place["lon"])
        if distance <= radius:
            places.append({**place, "distance_m": distance})
    places.sort(key=lambda place: (place["distance_m"], place["id"]))
    return {"places": places[:120], "total": len(places), "limit": 120, "radius_m": radius,
            "center": {"lat": lat, "lon": lon}, "bounds": BOUNDS,
            "source": data["source"], "source_timestamp": data["source_timestamp"],
            "retrieved_at": data["retrieved_at"], "coverage": data["coverage"],
            "availability": "unknown"}


@router.get("/dataset")
def dataset():
    return FileResponse(DATA, media_type="application/json", filename="civic-london-parking-odbl.json")


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=160)):
    """Explicit searches only; cached and throttled. Swap Photon through configuration."""
    global _last_search
    query = " ".join(q.split())
    if len(query) < 2:
        raise HTTPException(422, "Enter a London place or postcode.")
    key = query.casefold()
    with _search_lock:
        cached = _search_cache.get(key)
        if cached and time.monotonic() - cached[0] < 86400:
            _search_cache.move_to_end(key)
            return {"results": cached[1]}
        if time.monotonic() - _last_search < 1:
            raise HTTPException(429, "Please wait a moment before searching again.", headers={"Retry-After": "1"})
        _last_search = time.monotonic()
    try:
        response = httpx.get(os.getenv("PARKING_GEOCODER_URL", "https://photon.komoot.io/api/"),
            params={"q": query, "limit": 6, "lang": "en", "lat": 51.51, "lon": -0.13,
                    "bbox": ",".join(str(n) for n in BOUNDS)},
            headers={"User-Agent": "CivicParking/1.0 (https://mubit-hunters.onrender.com)"}, timeout=8)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ValueError("Missing geocoding results")
        results, seen = [], set()
        for feature in payload["features"][:6]:
            if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict):
                continue
            coordinates = feature.get("geometry", {}).get("coordinates", [])
            if not isinstance(coordinates, list) or len(coordinates) != 2:
                continue
            lon, lat = coordinates
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not in_coverage(lat, lon):
                continue
            properties = feature.get("properties") or {}
            if not isinstance(properties, dict):
                continue
            name = properties.get("name") or properties.get("street") or properties.get("postcode") or query
            address = ", ".join(dict.fromkeys(str(properties[k]) for k in ("street", "district", "city", "postcode")
                                              if properties.get(k) and properties[k] != name))
            identity = (str(name).casefold(), address.casefold())
            if identity in seen:
                continue
            seen.add(identity)
            results.append({"id": f"{properties.get('osm_type', '')}/{properties.get('osm_id', len(results))}",
                            "name": str(name)[:160], "address": address[:250], "lat": lat, "lon": lon})
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise HTTPException(503, "Place search is unavailable right now. You can still explore the map or use your location.")
    with _search_lock:
        _search_cache[key] = (time.monotonic(), results)
        while len(_search_cache) > 200:
            _search_cache.popitem(last=False)
    return {"results": results}
