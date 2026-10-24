# Public parking map

Reviewed **24 October 2026**. **[Open the hosted map](https://mubit-hunters.onrender.com/#parking)** · [Capacity and service limits](CAPACITY.md).

Open `/#parking` from the public consumer home. The existing authenticated council workspace is at `/#workspace`. The surrounding driver signup, ticket reading and appeal flow are documented in [CONSUMER.md](CONSUMER.md).

## What works

- Search a London destination or postcode, use the three area shortcuts, move the map and select **Search this area**, or explicitly request browser location access.
- Browse a matching map and distance-sorted list, with clustered pins, selection details, light/dark themes, and mobile map/list switching.
- Filter covered parking, recorded free parking, or recorded accessible bays. Unknown facts never qualify as free/accessible. Customer-only access and conditional charges remain visible.
- View known opening hours, charges, maximum stay, height limits and access conditions. Open the operator's site, the original OSM record or driving directions.
- Map failures leave the list usable; geocoder failures leave map browsing usable. No API key is needed for the initial map.

## Data and architecture

```text
React / MapLibre ── /api/parking/nearby ── FastAPI ── bundled London snapshot
        │
        ├───────── /api/parking/search ── FastAPI ── Photon place search
        └───────── OpenFreeMap vector tiles / styles
```

The snapshot contains **4,339 mapped parking locations**, extracted from OpenStreetMap on **24 October 2026**, source timestamp **2026-10-24T17:20:01Z**. Coverage is a bounding box around London and its immediate surroundings, not a jurisdiction boundary or complete inventory. Locations are car parks/parking areas, not a count of individual vacant bays. Explicitly private, resident-only, permit-only, closed and designated bus/coach/lorry facilities are excluded where those restrictions are tagged. Incomplete OSM tags can still omit restrictions: the interface asks users to check current signs and tariffs.

Each nearby request calculates straight-line distance from the destination, returning the nearest 120 locations within 2.5 km by default. The read-only snapshot is cached in process. No database migrations or Neon tables are needed. These three GET endpoints are public; case data remains behind the existing session gate.

The map and its worker load in a separate bundle. OpenFreeMap supplies tiles directly to the browser. Photon searches happen only on form submission, with an eight-second timeout, 24-hour in-process cache (200 queries) and a global one-request-per-second limit per server process. No location history is added to the application database; ordinary server/provider request logs may contain queries or coordinates.

Mubit is not needed to place factual map pins or filter source attributes. A future Mubit planning tool can query this same data when helping a user choose parking, while keeping prices, restrictions and availability grounded in the source.

## Licensing and refresh

The derived dataset is available at `/api/parking/dataset` under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), with [OpenStreetMap attribution](https://www.openstreetmap.org/copyright) on the map and page. Source links are retained per place. The packaged application code's existing licensing is unchanged.

Refresh manually from the repository root:

```sh
.venv/bin/python backend/refresh_parking_data.py
# Or use an already downloaded Overpass response:
.venv/bin/python backend/refresh_parking_data.py --input /path/to/overpass.json
```

The script performs one bounded extract and atomically replaces `backend/data/parking-london.json`. Incomplete/suspiciously small responses preserve the old dataset. Review the changed dataset and rebuild/restart the application to use it. Do not call public Overpass for every map movement or user request.

## Deployment and limits

The existing Docker build copies the snapshot into the Render image and builds the frontend. No new Render secret is required. The browser needs HTTPS access to `tiles.openfreemap.org`; the backend needs HTTPS access to Photon. Existing Neon/workspace configuration still applies.

`PARKING_GEOCODER_URL` optionally replaces the default `https://photon.komoot.io/api/` with a compatible service. The public Photon instance has no service guarantee: use a hosted or self-hosted provider before a significant public launch, and use shared rate limits/caching for multiple server instances. See [Photon's usage guidance](https://github.com/komoot/photon) and [OpenFreeMap's quick start](https://openfreemap.org/quick_start/).

**Not connected:** live occupancy, reservations, current journey times, guaranteed pricing, nationwide coverage, or a live council/operator feed. Never market the map's location count as spaces available, cases helped or model training data.

## Focused checks

```sh
PCN_TEST_DATABASE_URL='' .venv/bin/python -m pytest backend/tests/test_parking.py -q
cd frontend
npm test
npm run build
```

Browser checks cover map loading, location selection, search, filters, directions links, mobile layout, and both themes. Actual device geolocation requires the user's permission and was not exercised during development.
