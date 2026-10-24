import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {Map as LibreMap, NavigationControl, AttributionControl, setWorkerUrl} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import "./parking.css";
import {Icon} from "./Icons.jsx";
import {api} from "./api.js";
import {LONDON, COVERAGE, accessLabel, directionsUrl, distanceLabel, hasAccessibleBays, inCoverage, matchesFilter, priceLabel, typeLabel} from "./parking.js";

setWorkerUrl(workerUrl);
const styles = {light: "https://tiles.openfreemap.org/styles/positron", dark: "https://tiles.openfreemap.org/styles/dark"};
const emptyFeatures = {type: "FeatureCollection", features: []};
const shortcuts = [LONDON, {lat: 51.5033, lon: -0.1147, name: "Waterloo, London"}, {lat: 51.5413, lon: -0.0033, name: "Stratford, London"}];

export default function ParkingMap({theme}) {
  const container = useRef(null), controls = useRef(null), explorer = useRef(null), map = useRef(null), resultRefs = useRef(new window.Map());
  const [destination, setDestination] = useState(LONDON);
  const [data, setData] = useState(null), [busy, setBusy] = useState(true), [error, setError] = useState("");
  const [filter, setFilter] = useState("all"), [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState(""), [searching, setSearching] = useState(false), [suggestions, setSuggestions] = useState(null), [searchError, setSearchError] = useState("");
  const [locating, setLocating] = useState(false), [locationError, setLocationError] = useState("");
  const [moved, setMoved] = useState(false), [mapError, setMapError] = useState(""), [ready, setReady] = useState(false);
  const [mobileView, setMobileView] = useState("map"), [mapVersion, setMapVersion] = useState(0), [requestVersion, setRequestVersion] = useState(0);
  const searchRequest = useRef(0), currentTheme = useRef(theme), mapTheme = useRef(theme);
  const visible = useMemo(() => (data?.places || []).filter(place => matchesFilter(place, filter)), [data, filter]);
  const selected = visible.find(place => place.id === selectedId) || null;
  const latest = useRef({visible, selectedId, destination});
  latest.current = {visible, selectedId, destination};
  currentTheme.current = theme;

  const selectPlace = useCallback((id, fromMap = false) => {
    setSelectedId(id);
    if (!fromMap) setMobileView("map");
    const place = latest.current.visible.find(item => item.id === id);
    if (place && map.current) map.current.flyTo({center: [place.lon, place.lat], zoom: Math.max(map.current.getZoom(), 15.5),
      offset: [0, -Math.min(180, map.current.getContainer().clientHeight * .37)], duration: 700});
    if (fromMap) {
      const item = resultRefs.current.get(id), list = item?.parentElement;
      if (list && item) list.scrollTo({top: item.offsetTop - list.offsetTop, behavior: "smooth"});
    }
  }, []);

  useEffect(() => {
    const resize = new ResizeObserver(() => explorer.current?.style.setProperty("--parking-controls-height", `${controls.current.offsetHeight}px`));
    resize.observe(controls.current);
    return () => resize.disconnect();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError(""); setData(null); setSelectedId(null);
    api.parkingNearby(destination, {signal: controller.signal}).then(result => {
      setData(result); setSelectedId(null); setMoved(false);
    }).catch(err => {if (err.name !== "AbortError") {setError(err.message); setData(null);}})
      .finally(() => {if (!controller.signal.aborted) setBusy(false);});
    return () => controller.abort();
  }, [destination, requestVersion]);

  useEffect(() => {
    setReady(false); setMapError("");
    let instance;
    try {
      instance = new LibreMap({container: container.current, style: styles[currentTheme.current],
        center: [latest.current.destination.lon, latest.current.destination.lat], zoom: 14.2, minZoom: 10, maxZoom: 19,
        maxBounds: [[COVERAGE.west - .1, COVERAGE.south - .07], [COVERAGE.east + .1, COVERAGE.north + .07]],
        attributionControl: false, pitchWithRotate: false, dragRotate: false});
    } catch {
      setMapError("Your browser couldn’t open the map. The parking list is still available.");
      return;
    }
    map.current = instance;
    mapTheme.current = currentTheme.current;
    instance.addControl(new NavigationControl({showCompass: false}), "top-right");
    instance.addControl(new AttributionControl({compact: true}), "bottom-left");
    instance.getCanvas().setAttribute("aria-label", "London parking map. The same locations are available in the parking results list.");
    const timer = setTimeout(() => {if (!instance.isStyleLoaded()) setMapError("The map is taking longer to load. You can still browse the parking list.");}, 15000);
    instance.on("style.load", () => {
      setMapError(""); setReady(true);
      if (!instance.getSource("parking")) {
        instance.addSource("parking", {type: "geojson", data: emptyFeatures, cluster: true, clusterMaxZoom: 14, clusterRadius: 38});
        instance.addLayer({id: "clusters", type: "circle", source: "parking", filter: ["has", "point_count"], paint: {
          "circle-color": "#d6f766", "circle-radius": ["step", ["get", "point_count"], 20, 10, 24, 30, 29],
          "circle-stroke-width": 2, "circle-stroke-color": "#25362c"}});
        instance.addLayer({id: "cluster-count", type: "symbol", source: "parking", filter: ["has", "point_count"], layout: {
          "text-field": "{point_count_abbreviated}", "text-font": ["Noto Sans Bold"], "text-size": 13,
          "text-allow-overlap": true, "text-ignore-placement": true}, paint: {"text-color": "#203026"}});
        instance.addLayer({id: "parking-point", type: "circle", source: "parking", filter: ["!", ["has", "point_count"]], paint: {
          "circle-color": ["case", ["get", "selected"], "#d6f766", "#3158e8"], "circle-radius": ["case", ["get", "selected"], 19, 14],
          "circle-stroke-width": 2.5, "circle-stroke-color": "#fffdf8"}});
        instance.addLayer({id: "parking-label", type: "symbol", source: "parking", filter: ["!", ["has", "point_count"]], layout: {
          "text-field": "P", "text-font": ["Noto Sans Bold"], "text-size": 13, "text-allow-overlap": true},
          paint: {"text-color": ["case", ["get", "selected"], "#203026", "#ffffff"]}});
        instance.addSource("destination", {type: "geojson", data: emptyFeatures});
        instance.addLayer({id: "destination-halo", type: "circle", source: "destination", paint: {"circle-radius": 18, "circle-color": "#f5975c", "circle-opacity": .25}});
        instance.addLayer({id: "destination-point", type: "circle", source: "destination", paint: {"circle-radius": 6, "circle-color": "#df632c", "circle-stroke-color": "#fffdf8", "circle-stroke-width": 2}});
      }
      updateMap(instance, latest.current);
    });
    instance.on("click", "clusters", async event => {
      const feature = event.features?.[0];
      if (!feature) return;
      try {
        const zoom = await instance.getSource("parking").getClusterExpansionZoom(feature.properties.cluster_id);
        if (map.current === instance) instance.easeTo({center: feature.geometry.coordinates, zoom});
      } catch { /* A style change may remove an in-flight cluster. */ }
    });
    instance.on("click", "parking-point", event => {const id = event.features?.[0]?.properties.id; if (id) selectPlace(id, true);});
    for (const layer of ["clusters", "parking-point"]) {
      instance.on("mouseenter", layer, () => {instance.getCanvas().style.cursor = "pointer";});
      instance.on("mouseleave", layer, () => {instance.getCanvas().style.cursor = "";});
    }
    instance.on("dragend", () => setMoved(true));
    instance.on("zoomend", event => {if (event.originalEvent) setMoved(true);});
    const resize = new ResizeObserver(() => instance.resize());
    resize.observe(container.current);
    return () => {clearTimeout(timer); resize.disconnect(); instance.remove(); if (map.current === instance) map.current = null;};
  }, [mapVersion, selectPlace]);

  useEffect(() => {if (ready && map.current?.getSource("parking")) updateMap(map.current, {visible, selectedId, destination});}, [visible, selectedId, destination, ready]);
  useEffect(() => {if (map.current && mapTheme.current !== theme) {mapTheme.current = theme; setReady(false); map.current.setStyle(styles[theme]);}}, [theme]);
  useEffect(() => {if (selectedId && !visible.some(place => place.id === selectedId)) setSelectedId(null);}, [visible, selectedId]);
  useEffect(() => {map.current?.resize();}, [mobileView]);
  useEffect(() => () => {searchRequest.current += 1;}, []);

  function goTo(place) {
    searchRequest.current += 1; setSearching(false); setSuggestions(null); setSearchError(""); setLocationError("");
    setQuery(place.name); setDestination(place); setSelectedId(null); setMoved(false); setMobileView("map");
    map.current?.flyTo({center: [place.lon, place.lat], zoom: 14.2, duration: 900});
  }
  async function search(event) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    const id = ++searchRequest.current;
    setSearching(true); setSuggestions(null); setSearchError("");
    try {
      const result = await api.parkingSearch(query.trim());
      if (id !== searchRequest.current) return;
      setSuggestions(result.results);
      if (!result.results.length) setSearchError("No London places found. Try a nearby landmark or postcode.");
    } catch (err) {if (id === searchRequest.current) setSearchError(err.message);}
    finally {if (id === searchRequest.current) setSearching(false);}
  }
  function locate() {
    if (!navigator.geolocation) {setLocationError("Location isn’t supported here. Search a place instead."); return;}
    setLocating(true); setLocationError("");
    navigator.geolocation.getCurrentPosition(({coords}) => {
      setLocating(false);
      if (!inCoverage(coords.latitude, coords.longitude)) {setLocationError("You’re outside our London coverage. Search a London destination instead."); return;}
      goTo({lat: coords.latitude, lon: coords.longitude, name: "Your location"});
    }, () => {setLocating(false); setLocationError("Location wasn’t available. You can search a place or postcode instead.");}, {timeout: 10000, maximumAge: 60000});
  }
  function searchArea() {
    const center = map.current?.getCenter();
    if (!center) return;
    if (!inCoverage(center.lat, center.lng)) {setLocationError("Move the map inside London to search this area."); return;}
    setDestination({lat: center.lat, lon: center.lng, name: "This map area"}); setMoved(false);
  }

  return <main id="main-content" className="parking-page">
    <div className="parking-heading"><div><div className="eyebrow">A LITTLE PLANNING. A BETTER ARRIVAL.</div><h1>Find your space<span className="blue">.</span></h1><p>A clearer view of where to park, before you get there.</p></div><span className="parking-city-stamp"><span className="live-dot"/>LONDON EDITION <Icon name="pin" size={15}/></span></div>
    <section ref={explorer} className={`parking-explorer view-${mobileView}`} aria-label="Find parking in London">
      <aside className="parking-sidebar">
        <div ref={controls} className="parking-controls">
        <div className="parking-search-panel">
          <label htmlFor="parking-search" className="parking-label">Where are you heading?</label>
          <form className="parking-search-form" onSubmit={search}><Icon name="search" size={19}/><input id="parking-search" autoComplete="off" placeholder="Place, address or postcode" value={query} maxLength={160} onChange={event => {setQuery(event.target.value); setSuggestions(null); searchRequest.current += 1; setSearching(false);}} onKeyDown={event => {if (event.key === "Escape") setSuggestions(null);}}/><button type="submit" aria-label="Search London places" disabled={searching || query.trim().length < 2}>{searching ? <span className="spinner"/> : <Icon name="arrow" size={19}/>}</button></form>
          {suggestions?.length > 0 && <div className="parking-search-results" aria-label="Matching destinations">{suggestions.map((place, index) => <button key={`${place.id}-${index}`} onClick={() => goTo(place)}><Icon name="pin" size={16}/><span><strong>{place.name}</strong><small>{place.address || "London"}</small></span><Icon name="arrow" size={14}/></button>)}</div>}
          {searchError && <p role="status" className="parking-inline-error">{searchError}</p>}
          <div className="parking-shortcuts">{shortcuts.map(place => <button key={place.name} onClick={() => goTo(place)}>{place.name.split(",")[0]}</button>)}<button className="parking-locate" onClick={locate} disabled={locating}><Icon name="locate" size={13}/>{locating ? "Locating…" : "Near me"}</button></div>
          {locationError && <p role="status" className="parking-inline-error">{locationError}</p>}
        </div>
        <div className="parking-filter-bar" role="group" aria-label="Filter parking">{[["all", "All parking"], ["covered", "Covered"], ["free", "Free"], ["accessible", "Accessible bays"]].map(([value, label]) => <button key={value} aria-pressed={filter === value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>)}</div>
        </div>
        <div className="parking-results-heading"><div><h2>{destination.name}</h2><p>{busy ? "Finding nearby parking…" : `${visible.length} mapped locations · within 2.5 km`}</p></div><span className="parking-sort"><Icon name="sort" size={13}/>Nearest</span></div>
        <div className="parking-results" aria-label="Parking results" aria-busy={busy}>
          {busy ? <div className="parking-skeletons" role="status" aria-label="Loading nearby parking">{[0, 1, 2, 3].map(i => <div className="parking-skeleton" key={i}><span/><span/><span/></div>)}</div> : error ? <div className="parking-empty" role="alert"><Icon name="pin" size={28}/><h3>We couldn’t load these places.</h3><p>{error}</p><button className="btn" onClick={() => setRequestVersion(v => v + 1)}>Try again</button></div> : !visible.length ? <div className="parking-empty" role="status"><Icon name="search" size={28}/><h3>{filter === "all" ? "No mapped parking nearby." : "No matches for this filter."}</h3><p>{filter === "all" ? "Try another area. Map coverage is not a complete inventory of parking." : "Missing access or price information isn’t treated as a match."}</p><button className="btn" onClick={() => filter === "all" ? goTo(LONDON) : setFilter("all")}>{filter === "all" ? "Explore central London" : "Show all parking"}</button></div> : visible.map((place, index) => <button ref={node => {if (node) resultRefs.current.set(place.id, node); else resultRefs.current.delete(place.id);}} key={place.id} className={`parking-result ${selectedId === place.id ? "selected" : ""}`} aria-pressed={selectedId === place.id} onClick={() => selectPlace(place.id)}>
            <div className="parking-result-top"><span className="parking-type-symbol">P<small>{String(index + 1).padStart(2, "0")}</small></span><div><span className="parking-type">{typeLabel(place)}</span><h3>{place.name}</h3></div><Icon name="arrow" size={16}/></div>
            <div className="parking-result-meta"><span><Icon name="pin" size={12}/>{distanceLabel(place.distance_m)} away</span><span className={place.access !== "public" ? "parking-access-note" : ""}>{accessLabel(place)}</span></div>
            <div className="parking-result-bottom"><strong>{priceLabel(place)}</strong><span>{place.covered ? <><Icon name="garage" size={13}/>Covered</> : hasAccessibleBays(place) ? "Accessible bays listed" : "View details"}</span></div>
          </button>)}
          {data?.total > data?.limit && !busy && <p className="parking-list-note">Showing the nearest {data.limit} of {data.total} mapped locations. Move the map to explore more.</p>}
        </div>
        <div className="parking-sidebar-footer"><Icon name="info" size={14}/><span>Distances are straight-line. Spaces are not reserved.</span></div>
      </aside>
      <div className="parking-map-panel">
        <div ref={container} className="parking-map-canvas"/>
        {!ready && !mapError && <div className="parking-map-loading" role="status"><span className="spinner"/>Opening the map…</div>}
        {mapError && <div className="parking-map-error" role="status"><Icon name="map" size={26}/><p>{mapError}</p><button className="btn" onClick={() => setMapVersion(v => v + 1)}>Reload map</button><button className="text-btn" onClick={() => setMobileView("list")}>Browse the list</button></div>}
        <div className="parking-map-top"><span className="parking-map-label"><span className="destination-dot"/>Around {destination.name}</span>{moved && <button className="parking-search-area" onClick={searchArea} disabled={busy}><Icon name="search" size={15}/>Search this area</button>}</div>
        <div className="parking-map-legend"><span><i className="parking-dot"/>Parking</span><span><i className="destination-dot"/>Destination</span></div>
        <div className="parking-map-bottom">
          {selected ? <ParkingDetails place={selected} onClose={() => setSelectedId(null)}/> : <div className="parking-map-tip"><span className="parking-tip-icon"><Icon name="spark" size={21}/></span><div><strong>A good spot starts with the details.</strong><p>Tap a P to check access, prices and directions.</p></div><span className="parking-tip-squiggle" aria-hidden="true">↗</span></div>}
          <p className="parking-availability"><span/>Live space availability isn’t connected. Check on arrival.</p>
        </div>
      </div>
      <div className="parking-mobile-toggle" role="group" aria-label="Parking view"><button aria-pressed={mobileView === "map"} onClick={() => setMobileView("map")}><Icon name="map" size={16}/>Map</button><button aria-pressed={mobileView === "list"} onClick={() => setMobileView("list")}><Icon name="inbox" size={16}/>List{!busy && <span>{visible.length}</span>}</button></div>
    </section>
    <footer className="parking-provenance"><p>Location data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a> · {data ? `Snapshot ${new Date(data.retrieved_at).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric"})}` : "London coverage"} · <a href="/api/parking/dataset" download>Download source data</a></p><span>Always check current signs and tariffs.</span></footer>
  </main>;
}

function updateMap(map, {visible, selectedId, destination}) {
  map.getSource("parking")?.setData({type: "FeatureCollection", features: visible.map(place => ({type: "Feature", properties: {id: place.id, selected: place.id === selectedId}, geometry: {type: "Point", coordinates: [place.lon, place.lat]}}))});
  map.getSource("destination")?.setData({type: "FeatureCollection", features: [{type: "Feature", properties: {}, geometry: {type: "Point", coordinates: [destination.lon, destination.lat]}}]});
}

function ParkingDetails({place, onClose}) {
  const facts = [["Price", priceLabel(place)], ["Access", accessLabel(place)], ["Hours", place.hours || "Not recorded"],
    ["Maximum stay", place.maxstay || "Check signs"], ...(place.height_limit ? [["Height limit", place.height_limit]] : []),
    ...(place.disabled_bays ? [["Accessible bays", place.disabled_bays]] : [])];
  return <section className="parking-detail" aria-label={`Details for ${place.name}`}>
    <div className="parking-detail-heading"><div><span className="parking-type">{typeLabel(place)} · {distanceLabel(place.distance_m)} from destination</span><h2>{place.name}</h2>{place.address && <p>{place.address}</p>}</div><button className="icon-btn" aria-label="Close parking details" onClick={onClose}><Icon name="close"/></button></div>
    <dl className="parking-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    {place.fee_condition && <p className="parking-conditions">Charge conditions: {place.fee_condition}</p>}
    {place.access_condition && <p className="parking-conditions">Access conditions: {place.access_condition}</p>}
    {place.reservation && place.reservation !== "no" && <p className="parking-conditions">Reservation: {place.reservation}</p>}
    <div className="parking-detail-actions"><a className="btn primary" href={directionsUrl(place)} target="_blank" rel="noreferrer"><Icon name="navigate" size={16}/>Get directions</a>{place.website && <a className="btn" href={place.website} target="_blank" rel="noreferrer">Operator website<Icon name="external" size={13}/></a>}<a className="text-btn" href={place.source_url} target="_blank" rel="noreferrer">View source<Icon name="external" size={12}/></a></div>
    <p className="parking-detail-note">Map details may change. Confirm the entrance, signs and current tariff before parking.</p>
  </section>;
}
