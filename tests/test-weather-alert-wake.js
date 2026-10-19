const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'weather-alerts.js'), 'utf8');
const serviceWorker = fs.readFileSync(path.join(__dirname, '..', 'sw.js'), 'utf8');

test('offline app shell caches the alert helper with a new cache version', () => {
  assert.match(serviceWorker, /dayglance-shell-v12/);
  assert.match(serviceWorker, /'\.\/weather-alerts\.js'/);
});

function helpers(){
  const window = {};
  vm.runInNewContext(source, {window, Map, Set, Array, String});
  return window.DayglanceAlertWake;
}

test('returns an unseen alert until a successful wake marks it seen', () => {
  const alert = {id: 'synthetic-alert-1', properties: {event: 'Severe Thunderstorm Warning'}};
  const seen = new Set();
  const wake = helpers();
  assert.deepEqual(Array.from(wake.unseen([alert], seen)), ['synthetic-alert-1']);
  assert.deepEqual(Array.from(wake.unseen([{...alert, properties: {event: 'Warning continued'}}], seen)), ['synthetic-alert-1']);
  wake.markSeen(['synthetic-alert-1'], seen);
  assert.deepEqual(Array.from(wake.unseen([{...alert, properties: {event: 'Warning continued'}}], seen)), []);
});

test('deduplicates the same alert when it affects multiple locations', () => {
  const alert = {id: 'synthetic-alert-1'};
  const seen = new Set();
  const wake = helpers();
  assert.equal(wake.unseen([alert], seen).length, 1);
  assert.equal(wake.unseen([alert], seen).length, 1);
  wake.markSeen(['synthetic-alert-1'], seen);
  assert.equal(wake.unseen([alert], seen).length, 0);
});

test('uses stable synthetic fields when a provider omits an alert ID', () => {
  const seen = new Set();
  const wake = helpers();
  const alert = {properties: {event: 'Warning', areaDesc: 'Example County', effective: '2026-10-19T18:00:00Z', headline: 'Take shelter'}};
  const first = wake.unseen([alert], seen);
  assert.equal(first.length, 1);
  wake.markSeen(first, seen);
  assert.deepEqual(Array.from(wake.unseen([alert], seen)), []);
});

test('ignores alerts with no stable identity fields', () => {
  assert.deepEqual(Array.from(helpers().unseen([{properties: {}}], new Set())), []);
});

test('does not wake for stale data, hidden pages, or a city that is not displayed', () => {
  const alert = {id: 'synthetic-alert-2'};
  const seen = new Set();
  const wake = helpers();
  assert.deepEqual(Array.from(wake.markForCurrentLocation('city-a', 'city-a', {stale: true}, [alert], seen)), []);
  assert.deepEqual(Array.from(wake.markForCurrentLocation('city-a', 'city-a', {stale: false}, [alert], seen, false)), []);
  assert.deepEqual(Array.from(wake.markForCurrentLocation('city-a', 'city-b', {stale: false}, [alert], seen)), []);
  assert.equal(seen.size, 0);
  assert.deepEqual(Array.from(wake.markForCurrentLocation('city-a', 'city-a', {stale: false}, [alert], seen)), ['synthetic-alert-2']);
});
