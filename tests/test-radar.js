const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'radar.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
const config = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config.json'), 'utf8'));

function makeRadar({configured = false, snapshotOk = true} = {}) {
  const elements = new Map();
  const timers = new Map();
  const radarLayers = [];
  let nextTimer = 1;

  class Element {
    constructor(id) {
      this.id = id;
      this.listeners = {};
      this.attributes = {};
      this.textContent = '';
      this.value = '';
      this.title = '';
      this.disabled = false;
      this.hidden = false;
      const classes = new Set();
      this.classList = {
        add: name => classes.add(name),
        remove: name => classes.delete(name),
        contains: name => classes.has(name),
        toggle: (name, force) => {
          const shouldAdd = force === undefined ? !classes.has(name) : Boolean(force);
          if (shouldAdd) classes.add(name); else classes.delete(name);
          return shouldAdd;
        }
      };
    }
    addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
    setAttribute(name, value) { this.attributes[name] = value; }
    getAttribute(name) { return this.attributes[name]; }
    async click() { for (const callback of this.listeners.click || []) await callback({target: this}); }
    dispatch(name) { for (const callback of this.listeners[name] || []) callback({target: this}); }
  }

  class Layer {
    constructor(url) { this.url = url; this.listeners = {}; }
    once(name, callback) { (this.listeners[name] ||= []).push({callback, once: true}); return this; }
    on(name, callback) { (this.listeners[name] ||= []).push({callback, once: false}); return this; }
    addTo() { if (this.url.includes('/api/radar/rainbow-tile/') || this.url.includes('rainviewer.com')) radarLayers.push(this); return this; }
    fire(name) {
      const handlers = this.listeners[name] || [];
      this.listeners[name] = handlers.filter(item => !item.once);
      for (const item of handlers) item.callback();
    }
  }

  const map = {
    setView() { return this; },
    invalidateSize() {},
    whenReady(callback) { callback(); },
    removeLayer() {}
  };
  const window = {
    L: {
      map: () => map,
      tileLayer: url => new Layer(url)
    },
    setTimeout(callback, delay) {
      const id = nextTimer++;
      timers.set(id, {callback, delay});
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    dispatchEvent() {},
    addEventListener() {}
  };
  const document = {
    querySelector(selector) {
      const id = selector.slice(1);
      if (!elements.has(id)) elements.set(id, new Element(id));
      return elements.get(id);
    }
  };
  const fetch = async url => {
    if (url === './api/radar/status') return {ok: true, json: async () => ({
      configured,
      canManage: true,
      usage: {month: '2026-10', tiles: 0, tileAllowance: 30000, nowcastAllowance: 5000, allowPaidUsage: false},
      remaining: {tiles: 30000}
    })};
    if (url === './api/radar/rainviewer-metadata') return {ok: true, json: async () => ({
      host: 'https://tilecache.rainviewer.com',
      radar: {past: [1700000000, 1700000600, 1700001200].map(time => ({time, path: `/v2/radar/${time}`}))}
    })};
    if (url === './api/radar/rainbow-snapshot') return {
      ok: snapshotOk,
      json: async () => snapshotOk ? {snapshot: 1791889800} : {error: 'Forecast data is still unavailable.'}
    };
    throw new Error(`Unexpected request: ${url}`);
  };
  // Leaflet is exposed as a browser global in production; mirror that binding
  // in this VM context so initializeMap() resolves its unqualified `L` name.
  const context = {document, window, L: window.L, fetch, Event, Intl, Date, Number, Array, String, Promise, RegExp, console, requestAnimationFrame: callback => callback()};
  vm.runInNewContext(source, context, {filename: 'radar.js'});
  // Provider status is refreshed after forecast metadata; allow the complete async
  // chain to settle before asserting that the first Rainbow tile was requested.
  const flush = async () => { for (let i = 0; i < 16; i += 1) await Promise.resolve(); };
  return {elements, timers, radarLayers, window, flush, open: window.DayglanceRadar.open, setIdleTimeout: window.DayglanceRadar.setIdleTimeout};
}

test('radar timeout is configurable and the JSON default is one minute', async () => {
  const radar = makeRadar();
  assert.equal(config.preferences.radarIdleTimeoutSeconds, 60);
  assert.deepEqual(config._documentation.preferences.radarIdleTimeoutSeconds.validValues, [15, 30, 60, 300]);
  for (const [value, label] of [[15, '15 seconds'], [30, '30 seconds'], [60, '1 minute'], [300, '5 minutes']]) {
    assert.match(html, new RegExp(`<option value="${value}">${label}</option>`));
  }

  await radar.open({name: 'Test City', latitude: 38.9, longitude: -77.0});
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 60000), 'new radar page uses the one-minute default');
  assert.equal(radar.setIdleTimeout(15), 15);
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 15000), 'changing the setting updates an open page immediately');
  assert.equal([...radar.timers.values()].some(timer => timer.delay === 60000), false);

  radar.elements.get('radar-screen').dispatch('touchmove');
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 15000), 'activity resets using the selected duration');
  assert.equal(radar.setIdleTimeout(300), 300);
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 300000));
  assert.equal(radar.setIdleTimeout(999), 60, 'unsupported values fall back to one minute');
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 60000));
});

test('hourly view return timer offers the radar timeout presets and retains existing options', () => {
  assert.equal(config.preferences.returnAfterSeconds, 60);
  assert.deepEqual(config._documentation.preferences.returnAfterSeconds.validValues, [0, 15, 30, 60, 90, 120, 300]);
  for (const [value, label] of [[15, '15 seconds'], [30, '30 seconds'], [60, '1 minute'], [90, '1 minute 30 seconds'], [120, '2 minutes'], [300, '5 minutes'], [0, 'Stay open until closed']]) {
    assert.match(html, new RegExp(`<option value="${value}">${label}</option>`));
  }
  assert.match(app, /!\[0,15,30,60,90,120,300\]\.includes\(Number\(preferences\.returnAfterSeconds\)\)/);
});

test('rain radar remains hidden until first-run location setup is complete', () => {
  assert.match(html, /<button[^>]*id="radar-open"[^>]*hidden>/);
  assert.match(app, /\$\('#radar-open'\)\.hidden=locations\.length===0/);
});

test('Past radar toggles off and the page closes after one idle minute', async () => {
  const radar = makeRadar();
  await radar.open({name: 'Test City', latitude: 38.9, longitude: -77.0});
  const past = radar.elements.get('radar-past');
  const future = radar.elements.get('radar-future');
  assert.equal(past.getAttribute('aria-pressed'), 'true');
  assert.equal(future.disabled, false, 'future mode remains selectable so missing setup can be explained');
  assert.match(radar.elements.get('radar-note').textContent, /Loading RainViewer radar tiles/);
  radar.radarLayers.at(-1).fire('load');
  assert.match(radar.elements.get('radar-note').textContent, /playing automatically/);
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 7000));

  const initialIdle = [...radar.timers.entries()].find(([, timer]) => timer.delay === 60000)[0];
  radar.elements.get('radar-screen').dispatch('touchmove');
  assert.equal(radar.timers.has(initialIdle), false, 'touch activity resets the idle timeout');
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 60000));

  await past.click();
  assert.equal(past.getAttribute('aria-pressed'), 'false');
  assert.equal(future.getAttribute('aria-pressed'), 'false');
  assert.equal(radar.elements.get('radar-frame-time').textContent, 'No radar selected');
  assert.match(radar.elements.get('radar-note').textContent, /Select a time range/);
  assert.equal([...radar.timers.values()].some(timer => timer.delay === 7000), false);

  const idle = [...radar.timers.entries()].find(([, timer]) => timer.delay === 60000);
  idle[1].callback();
  assert.equal(radar.elements.get('radar-screen').hidden, true);
});

test('Future mode explains missing Rainbow setup and does not load or autoplay', async () => {
  const radar = makeRadar({configured: false});
  await radar.open({name: 'Test City', latitude: 38.9, longitude: -77.0});
  await radar.elements.get('radar-future').click();
  assert.equal(radar.elements.get('radar-future').getAttribute('aria-pressed'), 'true');
  assert.equal(radar.elements.get('radar-future').classList.contains('needs-setup'), true);
  assert.equal(radar.elements.get('radar-future').textContent, 'Next 4 hours · Set up');
  assert.match(radar.elements.get('radar-toast').textContent, /API key not entered/);
  assert.match(radar.elements.get('radar-note').textContent, /Forecast setup needed/);
  const toastTimeout = [...radar.timers.values()].find(timer => timer.delay === 4500);
  assert.ok(toastTimeout, 'the missing-key hint is temporary');
  toastTimeout.callback();
  assert.equal(radar.elements.get('radar-toast').hidden, true);
  assert.equal(radar.radarLayers.some(layer => layer.url.includes('/api/radar/rainbow-tile/')), false);
  assert.equal([...radar.timers.values()].some(timer => timer.delay === 7000), false);
  await radar.elements.get('radar-future').click();
  assert.equal(radar.elements.get('radar-future').getAttribute('aria-pressed'), 'false');
  assert.match(radar.elements.get('radar-note').textContent, /Radar paused/);
});

test('Future playback waits for forecast metadata and visible tiles to load', async () => {
  const radar = makeRadar({configured: true});
  await radar.open({name: 'Test City', latitude: 38.9, longitude: -77.0});
  await radar.elements.get('radar-future').click();
  await radar.flush();
  assert.match(radar.elements.get('radar-note').textContent, /Loading Rainbow forecast tiles/);
  const futureLayer = radar.radarLayers.at(-1);
  assert.match(futureLayer.url, /\/api\/radar\/rainbow-tile\/1791889800\/0\//);
  assert.equal([...radar.timers.values()].some(timer => timer.delay === 7000), false);
  futureLayer.fire('load');
  assert.match(radar.elements.get('radar-note').textContent, /Rainbow forecast ready · playing automatically/);
  assert.ok([...radar.timers.values()].some(timer => timer.delay === 7000));
});

test('Future mode reports an unavailable forecast without starting playback', async () => {
  const radar = makeRadar({configured: true, snapshotOk: false});
  await radar.open({name: 'Test City', latitude: 38.9, longitude: -77.0});
  await radar.elements.get('radar-future').click();
  await radar.flush();
  assert.equal(radar.elements.get('radar-frame-time').textContent, 'Forecast data unavailable');
  assert.match(radar.elements.get('radar-note').textContent, /still unavailable/);
  assert.equal(radar.radarLayers.some(layer => layer.url.includes('/api/radar/rainbow-tile/')), false);
  assert.equal([...radar.timers.values()].some(timer => timer.delay === 7000), false);
});
