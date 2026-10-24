export const LONDON = {lat: 51.5136, lon: -0.1365, name: "Soho, London"};
export const COVERAGE = {west: -0.51, south: 51.28, east: 0.34, north: 51.70};

export function inCoverage(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= COVERAGE.south && lat <= COVERAGE.north && lon >= COVERAGE.west && lon <= COVERAGE.east;
}
export function distanceLabel(metres) {
  return metres < 1000 ? `${Math.round(metres / 10) * 10} m` : `${(metres / 1000).toFixed(1)} km`;
}
export function hasAccessibleBays(place) {
  return place.disabled_bays === "yes" || /^\d+$/.test(place.disabled_bays || "") && Number(place.disabled_bays) > 0;
}
export function matchesFilter(place, filter) {
  if (filter === "covered") return place.covered;
  if (filter === "free") return place.fee === "no" && !place.fee_condition && !place.charge;
  if (filter === "accessible") return hasAccessibleBays(place);
  return true;
}
export function priceLabel(place) {
  if (place.charge) return place.charge;
  if (place.fee_condition) return "Conditional charges";
  return place.fee === "no" ? "Free · listed" : place.fee === "yes" ? "Paid · tariff not listed" : "Price not listed";
}
export function accessLabel(place) {
  return place.access === "customers" ? "Customers only" : place.access === "public" ? "Public access listed" : "Check access";
}
export function typeLabel(place) {
  return ({underground: "Underground", "multi-storey": "Multi-storey", street_side: "Street parking", surface: "Car park", rooftop: "Rooftop"})[place.type] || "Car park";
}
export function directionsUrl(place) {
  return `https://www.google.com/maps/dir/?${new URLSearchParams({api: "1", destination: `${place.lat},${place.lon}`, travelmode: "driving"})}`;
}
