import test from "node:test";
import assert from "node:assert/strict";
import {matchesFilter, priceLabel, accessLabel, directionsUrl, inCoverage} from "./parking.js";

test("filters never infer free or accessible parking from missing data", () => {
  assert.equal(matchesFilter({}, "free"), false);
  assert.equal(matchesFilter({fee: "no", fee_condition: "yes @ (Mo-Fr)"}, "free"), false);
  assert.equal(matchesFilter({fee: "no"}, "free"), true);
  for (const value of [null, "unknown", "0", "no"]) assert.equal(matchesFilter({disabled_bays: value}, "accessible"), false);
  assert.equal(matchesFilter({disabled_bays: "2"}, "accessible"), true);
});

test("labels preserve unknown prices and customer restrictions", () => {
  assert.equal(priceLabel({}), "Price not listed");
  assert.equal(priceLabel({fee: "yes"}), "Paid · tariff not listed");
  assert.equal(priceLabel({fee: "no", fee_condition: "yes @ (Mo-Fr)"}), "Conditional charges");
  assert.equal(accessLabel({access: "customers"}), "Customers only");
  assert.equal(accessLabel({}), "Check access");
});

test("directions use the selected place coordinates and coverage excludes other cities", () => {
  const url = new URL(directionsUrl({lat: 51.51, lon: -.13}));
  assert.equal(url.hostname, "www.google.com");
  assert.equal(url.searchParams.get("destination"), "51.51,-0.13");
  assert.equal(url.searchParams.get("travelmode"), "driving");
  assert.equal(inCoverage(51.51, -.13), true);
  assert.equal(inCoverage(53.48, -2.24), false);
});
