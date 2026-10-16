/* RainViewer historical frames and Rainbow Weather forecast radar. */
(() => {
  const $ = selector => document.querySelector(selector);
  const screen = $('#radar-screen');
  const mapElement = $('#radar-map');
  const modeButtons = {past: $('#radar-past'), future: $('#radar-future')};
  let map = null;
  let radarLayer = null;
  let frames = {past: [], future: []};
  let mode = null;
  let currentLocation = null;
  let rainbowConfigured = false;
  let canManageKey = false;
  let paidUsageEnabled = false;
  let providerUsage = null;
  let reportingTileError = false;
  let playbackTimer = null;
  let idleTimer = null;
  let idleTimeoutMs = 60_000;
  let toastTimer = null;
  let selectionSerial = 0;
  let frameIndex = 0;

  function status(message) { $('#radar-note').textContent = message; }
  function setKeyStatus(message) { $('#radar-key-status').textContent = message; }
  function showToast(message) {
    const toast = $('#radar-toast');
    toast.textContent = message;
    toast.hidden = false;
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => {
      toast.hidden = true;
      toast.textContent = '';
      toastTimer = null;
    }, 4500);
  }

  async function refreshProviderStatus() {
    try {
      const response = await fetch('./api/radar/status', {cache: 'no-store'});
      const info = await response.json();
      if (!response.ok) throw new Error(info.error || 'Could not read provider usage.');
      const usage = info.usage, remaining = info.remaining;
      rainbowConfigured = Boolean(info.configured);
      canManageKey = Boolean(info.canManage);
      providerUsage = usage;
      paidUsageEnabled = usage.allowPaidUsage === true;
      $('#rainbow-key-remove').hidden = !rainbowConfigured;
      $('#rainbow-api-key').disabled = $('#rainbow-key-save').disabled = !canManageKey;
      $('#rainbow-key-remove').disabled = !canManageKey;
      $('#rainbow-paid-toggle').disabled = !canManageKey || !rainbowConfigured;
      $('#rainbow-paid-toggle').textContent = paidUsageEnabled ? 'Disable paid use' : 'Enable paid use';
      $('#rainbow-paid-toggle').setAttribute('aria-pressed', String(paidUsageEnabled));
      $('#paid-usage-state').textContent = paidUsageEnabled ? 'Currently enabled · provider charges may apply' : 'Currently disabled · stops at the local free limit';
      if (!canManageKey) setKeyStatus('To protect the account key, manage it from the local Dayglance screen on the Pi.');
      $('#radar-usage').textContent = `UTC month ${usage.month} · This device: ${usage.tiles.toLocaleString()} / ${usage.tileAllowance.toLocaleString()} Rainbow tiles used; estimated ${remaining.tiles.toLocaleString()} remain. Rainbow's separate ${usage.nowcastAllowance.toLocaleString()} point-nowcast calls are not used by the map. Account dashboard is authoritative.`;
      $('#radar-future').disabled = false;
      $('#radar-future').title = rainbowConfigured ? '' : 'Select to see how to enable forecast data';
      $('#radar-future').classList.toggle('needs-setup', !rainbowConfigured);
      $('#radar-future').setAttribute('aria-label', rainbowConfigured ? 'Next 4 hours forecast' : 'Next 4 hours forecast (API key needed)');
      $('#radar-future').textContent = rainbowConfigured ? 'Next 4 hours' : 'Next 4 hours · Set up';
      return info;
    } catch (error) {
      $('#radar-usage').textContent = error.message;
      $('#radar-future').disabled = false;
      $('#radar-future').classList.add('needs-setup');
      $('#radar-future').setAttribute('aria-label', 'Next 4 hours forecast (setup status unavailable)');
      $('#rainbow-api-key').disabled = $('#rainbow-key-save').disabled = $('#rainbow-key-remove').disabled = true;
      $('#rainbow-paid-toggle').disabled = true;
      return null;
    }
  }

  function loadLeaflet() {
    if (window.L) return Promise.resolve();
    if (window.dayglanceLeafletLoading) return window.dayglanceLeafletLoading;
    window.dayglanceLeafletLoading = new Promise((resolve, reject) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.append(link);
      const script = document.createElement('script');
      script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      script.onload = resolve;
      script.onerror = () => reject(new Error('Could not load the map library. Check this device’s internet connection.'));
      document.head.append(script);
    });
    return window.dayglanceLeafletLoading;
  }

  function initializeMap() {
    if (map || !currentLocation) return;
    map = L.map(mapElement, {zoomControl: true, minZoom: 3, maxZoom: 7, preferCanvas: true})
      .setView([currentLocation.latitude, currentLocation.longitude], 5);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      minZoom: 3, maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);
    map.whenReady(() => map.invalidateSize());
  }

  function formatFrameTime(timestamp) {
    return new Intl.DateTimeFormat(undefined, {weekday: 'short', hour: 'numeric', minute: '2-digit'}).format(new Date(timestamp * 1000));
  }

  function setFrame(index) {
    if (!mode) return;
    const list = frames[mode];
    if (!list.length) return;
    const safeIndex = Math.max(0, Math.min(index, list.length - 1));
    frameIndex = safeIndex;
    const frame = list[safeIndex];
    $('#radar-frame-time').textContent = `${mode === 'past' ? 'Observed' : 'Forecast'} · ${formatFrameTime(frame.validTime)}`;
    if (radarLayer) map.removeLayer(radarLayer);
    status(mode === 'past' ? 'Loading RainViewer radar tiles…' : 'Loading Rainbow forecast tiles…');
    if (mode === 'past') {
      const url = `${frame.host}${frame.path}/256/{z}/{x}/{y}/2/1_0.png`;
      radarLayer = L.tileLayer(url, {minZoom: 3, maxZoom: 7, opacity: .72, attribution: '<a href="https://www.rainviewer.com/">Weather data by RainViewer</a>'});
    } else {
      const url = `./api/radar/rainbow-tile/${frame.snapshot}/${frame.offset}/{z}/{x}/{y}`;
      radarLayer = L.tileLayer(url, {minZoom: 3, maxZoom: 7, opacity: .72, attribution: '<a href="https://developer.rainbow.ai/">Forecast tiles by Rainbow Weather</a>'});
    }
    const layer = radarLayer;
    let layerFailed = false;
    layer.once('load', () => {
      if (layerFailed || layer !== radarLayer || screen.hidden || !mode) return;
      status(mode === 'past' ? 'RainViewer radar ready · playing automatically' : 'Rainbow forecast ready · playing automatically');
      scheduleNextFrame();
    });
    layer.on('tileerror', async () => {
      if (layer !== radarLayer || reportingTileError) return;
      layerFailed = true;
      stopPlayback();
      reportingTileError = true;
      if (mode === 'future') {
        const info = await refreshProviderStatus();
        if (info && !info.usage.allowPaidUsage && Number(info.usage.tiles) >= Number(info.usage.tileAllowance)) {
          status('This device reached its Rainbow free tile allowance. Enable pay-as-you-go in Settings to continue.');
        } else {
          status('Rainbow forecast tiles have not loaded. Check the API key or provider availability.');
        }
      } else {
        status('RainViewer tiles have not loaded. Check the connection or try zooming out.');
      }
      window.setTimeout(() => { reportingTileError = false; }, 2000);
    });
    radarLayer.addTo(map);
  }

  function chooseMode(nextMode, {toggle = true} = {}) {
    const chosenMode = toggle && mode === nextMode ? null : nextMode;
    selectionSerial += 1;
    const selection = selectionSerial;
    stopPlayback();
    mode = chosenMode;
    for (const [name, button] of Object.entries(modeButtons)) button.setAttribute('aria-pressed', String(name === mode));
    if (radarLayer) map.removeLayer(radarLayer);
    radarLayer = null;
    if (!mode) {
      $('#radar-frame-time').textContent = 'No radar selected';
      status('Radar paused. Select a time range to load and play it.');
      return;
    }

    if (mode === 'future') {
      $('#radar-frame-time').textContent = 'Forecast data not loaded';
      if (!rainbowConfigured) {
        showToast('Rainbow API key not entered. Add one in Settings → Radar & Provider Account.');
        status('Forecast setup needed. Select Past 2 hours or add a Rainbow API key in Settings.');
        return;
      }
      if (providerUsage && !paidUsageEnabled && Number(providerUsage.tiles) >= Number(providerUsage.tileAllowance)) {
        status('This device reached its Rainbow free tile allowance. Enable pay-as-you-go in Settings to continue.');
        return;
      }
      if (!frames.future.length) {
        status('Loading forecast frames from Rainbow Weather…');
        loadFutureFrames().then(() => {
          if (selection !== selectionSerial || mode !== 'future') return;
          if (!frames.future.length) throw new Error('Rainbow has no forecast frames available right now.');
          setFrame(0);
        }).catch(error => {
          if (selection !== selectionSerial || mode !== 'future') return;
          $('#radar-frame-time').textContent = 'Forecast data unavailable';
          status(error.message || 'Rainbow forecast data is not available yet.');
        });
        return;
      }
    }

    if (!frames[mode].length) {
      $('#radar-frame-time').textContent = mode === 'future' ? 'Forecast data unavailable' : 'Past radar unavailable';
      status(mode === 'future' ? 'Rainbow forecast frames are unavailable right now.' : 'RainViewer past radar frames are temporarily unavailable.');
      return;
    }
    setFrame(0);
  }

  function stopPlayback() {
    if (playbackTimer) window.clearTimeout(playbackTimer);
    playbackTimer = null;
  }

  function scheduleNextFrame() {
    stopPlayback();
    if (!mode || frames[mode].length < 2 || screen.hidden) return;
    // Wait seven seconds after each visible tile set finishes loading.
    playbackTimer = window.setTimeout(() => {
      playbackTimer = null;
      if (!mode || screen.hidden) return;
      setFrame((frameIndex + 1) % frames[mode].length);
    }, 7000);
  }

  function resetIdleTimer() {
    if (idleTimer) window.clearTimeout(idleTimer);
    idleTimer = null;
    if (!screen.hidden) idleTimer = window.setTimeout(close, idleTimeoutMs);
  }

  function setIdleTimeout(seconds) {
    const supported = [15, 30, 60, 300];
    const value = Number(seconds);
    idleTimeoutMs = (supported.includes(value) ? value : 60) * 1000;
    if (!screen.hidden) resetIdleTimer();
    return idleTimeoutMs / 1000;
  }

  async function loadPastFrames() {
    const response = await fetch('./api/radar/rainviewer-metadata', {cache: 'no-store'});
    if (!response.ok) throw new Error('RainViewer radar is temporarily unavailable.');
    const metadata = await response.json();
    const host = metadata.host;
    if (!/^https:\/\/(?:tilecache\.)?rainviewer\.com$/i.test(host || '')) throw new Error('RainViewer returned an unexpected tile host.');
    frames.past = (metadata.radar?.past || []).map(frame => ({host, path: frame.path, validTime: frame.time}));
    if (!frames.past.length) throw new Error('RainViewer has no recent radar frames for this area.');
  }

  async function loadFutureFrames() {
    if (!rainbowConfigured) return;
    const response = await fetch('./api/radar/rainbow-snapshot', {cache: 'no-store'});
    const info = await response.json();
    if (!response.ok) throw new Error(info.error || 'Rainbow forecast is unavailable.');
    const snapshot = Number(info.snapshot);
    if (!Number.isFinite(snapshot)) throw new Error('Rainbow returned an invalid radar snapshot.');
    frames.future = Array.from({length: 25}, (_, index) => ({snapshot, offset: index * 600, validTime: snapshot + index * 600}));
  }

  async function open(location) {
    if (!location || !Number.isFinite(location.latitude) || !Number.isFinite(location.longitude)) return;
    currentLocation = location;
    screen.hidden = false;
    stopPlayback();
    selectionSerial += 1;
    mode = null;
    for (const button of Object.values(modeButtons)) {
      button.disabled = true;
      button.setAttribute('aria-pressed', 'false');
    }
    resetIdleTimer();
    $('#radar-title').textContent = `Rain radar · ${location.name}`;
    status('Loading recent radar…');
    try {
      await loadLeaflet();
      initializeMap();
      map.setView([location.latitude, location.longitude], 5);
      await refreshProviderStatus();
      try { await loadPastFrames(); } catch { frames.past = []; }
      for (const button of Object.values(modeButtons)) button.disabled = false;
      chooseMode('past', {toggle: false});
      requestAnimationFrame(() => map.invalidateSize());
    } catch (error) {
      status(error.message);
      for (const button of Object.values(modeButtons)) button.disabled = false;
    }
  }

  async function refresh() {
    if (screen.hidden || !currentLocation) return;
    const previousMode = mode;
    if (!previousMode) return;
    stopPlayback();
    status('Refreshing radar frames…');
    try {
      await refreshProviderStatus();
      if (previousMode === 'past') await loadPastFrames();
      else {
        frames.future = [];
        await loadFutureFrames();
      }
      if (mode === previousMode) chooseMode(previousMode, {toggle: false});
      requestAnimationFrame(() => map?.invalidateSize());
    } catch (error) { status(error.message); }
  }

  function close() {
    if (idleTimer) window.clearTimeout(idleTimer);
    idleTimer = null;
    stopPlayback();
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = null;
    $('#radar-toast').hidden = true;
    selectionSerial += 1;
    if (radarLayer && map) map.removeLayer(radarLayer);
    radarLayer = null;
    screen.hidden = true;
    window.dispatchEvent(new Event('dayglance-radar-close'));
  }

  async function saveKey() {
    const keyInput = $('#rainbow-api-key');
    const button = $('#rainbow-key-save');
    const apiKey = keyInput.value.trim();
    if (!apiKey) { setKeyStatus('Paste the API key from your Rainbow developer account first.'); return; }
    button.disabled = true;
    setKeyStatus('Checking the key with Rainbow…');
    try {
      const response = await fetch('./api/radar/credential', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({apiKey})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not save the key.');
      keyInput.value = '';
      rainbowConfigured = true;
      setKeyStatus('Key verified and saved on this device. Forecast frames are ready.');
      await refreshProviderStatus();
    } catch (error) { setKeyStatus(error.message); }
    finally { button.disabled = !canManageKey; }
  }

  async function removeKey() {
    const button = $('#rainbow-key-remove');
    button.disabled = true;
    try {
      const response = await fetch('./api/radar/credential', {method: 'DELETE'});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not remove the key.');
      rainbowConfigured = false;
      paidUsageEnabled = false;
      frames.future = [];
      if (mode === 'future') chooseMode(null, {toggle: false});
      setKeyStatus('Rainbow API key removed from this device.');
      await refreshProviderStatus();
    } catch (error) { setKeyStatus(error.message); }
    finally { button.disabled = !canManageKey; }
  }

  async function togglePaidUsage() {
    if (!canManageKey || !rainbowConfigured) return;
    const enabling = !paidUsageEnabled;
    if (enabling && !window.confirm('Enable Rainbow pay-as-you-go for this Dayglance device? Requests beyond the free allowance may incur charges. This local estimate cannot see other device or app usage.')) return;
    const button = $('#rainbow-paid-toggle');
    button.disabled = true;
    try {
      const response = await fetch('./api/radar/paid-usage', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({allowPaidUsage: enabling})});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not update the paid-usage preference.');
      await refreshProviderStatus();
      setKeyStatus(enabling ? 'Pay-as-you-go enabled for this device. Rainbow charges are controlled by your provider account.' : 'Pay-as-you-go disabled. This device stops requesting forecast tiles at its local free allowance.');
    } catch (error) { setKeyStatus(error.message); }
    finally { button.disabled = !canManageKey || !rainbowConfigured; }
  }

  $('#radar-close').addEventListener('click', close);
  $('#radar-past').addEventListener('click', () => chooseMode('past'));
  $('#radar-future').addEventListener('click', () => chooseMode('future'));
  for (const eventName of ['pointerdown', 'pointermove', 'touchstart', 'touchmove', 'wheel', 'keydown', 'click']) {
    screen.addEventListener(eventName, () => resetIdleTimer(), {passive: true});
  }
  $('#rainbow-key-save').addEventListener('click', saveKey);
  $('#rainbow-key-remove').addEventListener('click', removeKey);
  $('#rainbow-paid-toggle').addEventListener('click', togglePaidUsage);
  window.addEventListener('resize', () => { if (!screen.hidden && map) map.invalidateSize(); });
  window.DayglanceRadar = {open, close, refresh, refreshProviderStatus, setIdleTimeout};
  refreshProviderStatus();
})();
