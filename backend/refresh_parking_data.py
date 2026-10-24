"""Refresh the bounded London extract. Run manually; never from a user request."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.parking_data import BOUNDS, normalise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Use an already downloaded Overpass JSON response")
    parser.add_argument("--endpoint", default="https://overpass-api.de/api/interpreter")
    args = parser.parse_args()
    west, south, east, north = BOUNDS
    query = f"[out:json][timeout:60];nwr[amenity=parking]({south},{west},{north},{east});out center tags;"
    if args.input:
        raw = json.loads(args.input.read_text())
    else:
        request = Request(args.endpoint + "?" + urlencode({"data": query}), headers={
            "User-Agent": "CivicParking/1.0 (https://mubit-hunters.onrender.com)"})
        with urlopen(request, timeout=90) as response:
            raw = json.load(response)
    if raw.get("remark") or not raw.get("elements"):
        raise RuntimeError("Incomplete source response; the existing snapshot has been preserved.")
    places = [place for element in raw["elements"] if (place := normalise(element))]
    if len(places) < 100:
        raise RuntimeError("Unexpectedly small extract; the existing snapshot has been preserved.")
    snapshot = {"source": "OpenStreetMap contributors", "source_url": "https://www.openstreetmap.org/copyright",
        "license": "ODbL 1.0", "coverage": "London and immediate surrounding areas", "bounds": BOUNDS,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "source_timestamp": raw.get("osm3s", {}).get("timestamp_osm_base"), "places": places}
    target = Path(__file__).parent / "data" / "parking-london.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(target)
    print(f"Saved {len(places):,} attributed parking locations to {target}")


if __name__ == "__main__":
    main()
