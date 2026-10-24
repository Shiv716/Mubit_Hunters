"""Parking truthfulness, public/private boundary and bounded place search."""
import httpx

from app import parking
from app.parking_data import normalise


def test_source_filter_preserves_unknowns_and_excludes_restricted_parking():
    element = {"type": "node", "id": 42, "lat": 51.51, "lon": -.13,
               "tags": {"amenity": "parking", "name": "Example car park"}}
    place = normalise(element)
    assert place["fee"] == "unknown" and place["availability"] == "unknown"
    assert place["access"] == "unknown" and place["charge"] is None
    for access in ("private", "no", "residents", "permit"):
        assert normalise({**element, "tags": {**element["tags"], "access": access}}) is None
    assert normalise({**element, "tags": {**element["tags"], "tourist_bus": "designated"}}) is None
    assert normalise({**element, "tags": {**element["tags"], "motor_vehicle": "private"}}) is None
    assert normalise({**element, "lat": 53.48}) is None
    assert normalise({**element, "tags": {"amenity": "parking"}}) is None
    assert normalise({**element, "tags": {**element["tags"], "website": "javascript:alert(1)"}})["website"] is None


def test_public_nearby_and_dataset_never_open_the_case_workspace(client, monkeypatch):
    monkeypatch.setenv("PCN_ACCESS_KEY", "local-parking-test-password")
    response = client.get("/api/parking/nearby?lat=51.5136&lon=-0.1365&radius=800")
    assert response.status_code == 200
    data = response.json()
    distances = [p["distance_m"] for p in data["places"]]
    assert distances and distances == sorted(distances) and max(distances) <= 800
    assert data["source"] == "OpenStreetMap contributors" and data["source_timestamp"]
    assert data["availability"] == "unknown" and all(p["availability"] == "unknown" for p in data["places"])
    dataset = client.get("/api/parking/dataset").json()
    assert dataset["license"] == "ODbL 1.0" and len(dataset["places"]) > 100
    assert len({p["id"] for p in dataset["places"]}) == len(dataset["places"])
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/queue").status_code == 401
    assert client.post("/api/parking/nearby").status_code == 401
    assert client.get("/api/parking/nearby?lat=53.48&lon=-2.24").status_code == 422
    assert client.get("/api/parking/nearby?radius=999999").status_code == 422


def test_search_keeps_london_results_caches_and_throttles(client, monkeypatch):
    monkeypatch.setattr(parking, "_search_cache", parking.OrderedDict())
    monkeypatch.setattr(parking, "_last_search", 0)
    calls = []
    def response(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(200, request=httpx.Request("GET", url), json={"features": [
            {"geometry": {"coordinates": [-.11, 51.50]}, "properties": {"name": "Waterloo", "city": "London", "osm_id": 1}},
            {"geometry": {"coordinates": [-2.24, 53.48]}, "properties": {"name": "Elsewhere"}},
            {"geometry": None}, None]})
    monkeypatch.setattr(parking.httpx, "get", response)
    data = client.get("/api/parking/search?q=Waterloo").json()
    assert len(data["results"]) == 1 and data["results"][0]["name"] == "Waterloo"
    assert client.get("/api/parking/search?q=%20WATERLOO%20").json() == data
    assert len(calls) == 1 and calls[0]["params"]["bbox"] == "-0.51,51.28,0.34,51.7"
    assert client.get("/api/parking/search?q=Soho").status_code == 429
    assert client.get("/api/parking/search?q=%20%20").status_code == 422


def test_search_failure_is_recoverable_without_fake_results(client, monkeypatch):
    monkeypatch.setattr(parking, "_search_cache", parking.OrderedDict())
    monkeypatch.setattr(parking, "_last_search", 0)
    monkeypatch.setattr(parking.httpx, "get", lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request("GET", url), json=[]))
    result = client.get("/api/parking/search?q=Waterloo")
    assert result.status_code == 503 and "explore the map" in result.json()["detail"]
    assert client.get("/api/parking/nearby").status_code == 200
