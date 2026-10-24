import {afterEach, test} from "node:test";
import assert from "node:assert/strict";
import {api, clearReadCache} from "./api.js";

const response = (data, status = 200) => new Response(JSON.stringify(data), {status});
afterEach(clearReadCache);

test("returning to a case reuses one request, then refreshes after ten seconds", async t => {
  let now = 0, calls = 0, release;
  const pending = new Promise(resolve => {release = resolve;});
  t.mock.method(Date, "now", () => now);
  t.mock.method(globalThis, "fetch", async () => ++calls === 1 ? pending : response({version: calls}));
  const first = api.getCase(1), second = api.getCase(1);
  assert.equal(calls, 1);
  release(response({version: 1}));
  assert.deepEqual(await first, await second);
  assert.deepEqual(await api.getCase(1), {version: 1});
  assert.equal(calls, 1);
  now = 10_001;
  assert.deepEqual(await api.getCase(1), {version: 2});
  assert.equal(calls, 2);
});

test("edits, uploads and logout clear reads; an older response cannot refill the cache", async t => {
  let reads = 0, release;
  const pending = new Promise(resolve => {release = resolve;});
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    if (options.method) return response({ok: true});
    return ++reads === 1 ? pending : response({version: reads});
  });
  const old = api.getCase(1);
  await api.resolve(1, {outcome: "needs_investigation"});
  assert.deepEqual(await api.getCase(1), {version: 2});
  release(response({version: 1}));
  await old;
  assert.deepEqual(await api.getCase(1), {version: 2});
  await api.uploadEvidence(1, "E1", new Blob(["synthetic"]));
  assert.deepEqual(await api.getCase(1), {version: 3});
  await api.logout();
  assert.deepEqual(await api.getCase(1), {version: 4});
});

test("sessions stay uncached, errors retry, and access denial clears saved views", async t => {
  let sessions = 0, insights = 0, cases = 0;
  t.mock.method(globalThis, "fetch", async url => {
    if (url === "/api/session") return response({request: ++sessions});
    if (url === "/api/insights") return ++insights === 1 ? response({detail: "Unavailable"}, 503) : response({total: 17});
    if (url === "/api/access-requests") return response({detail: "Access denied"}, 403);
    return response({version: ++cases});
  });
  await api.session(); await api.session();
  assert.equal(sessions, 2);
  await assert.rejects(api.insights(), /Unavailable/);
  assert.deepEqual(await api.insights(), {total: 17});
  await api.getCase(1);
  await assert.rejects(api.accessRequests(), /Access denied/);
  assert.deepEqual(await api.getCase(1), {version: 2});
});
