# DevPi Air Quality Update — 2026-10-15

Dayglance's production kiosk was updated in place with the modeled air-quality feature from PR #6. The deployed application code matches commit `391e097a8db2cf73edba3d43f6e834b6769cb459`; the follow-up commit adds only deployment evidence and the live screenshot.

## Deployment

- Replaced only `app.js`, `air-quality.js`, `index.html`, `styles.css`, `server.py`, and `sw.js` in the existing installation.
- Kept the installation directory, loopback origin (`http://127.0.0.1:8081/`), Chromium profile, and service configuration in place.
- Did not copy, replace, or rewrite `config.json` or `device-settings.json`. Their SHA-256 fingerprints matched before and after deployment.
- Restarted the existing `dayglance.service` and `dayglance-kiosk.service`; both reported active afterward.

## Verification

HTTP 200 was confirmed for `/`, `/air-quality.js`, `/app.js`, `/styles.css`, `/sw.js`, and `/api/device-settings`. The device settings endpoint remained available. A live 800×480 DevPi screenshot shows the modeled U.S. AQI and PM2.5 estimate alongside current conditions; see [the screenshot](docs/images/devpi-air-quality-2026-10-15.png).

The PR's CI run #12 passed on the deployed application code. Physical touchscreen interaction and wake after a full screensaver interval were not retested during this update.

The AQI and PM2.5 values shown are model estimates, not local sensor readings. They vary with the selected location and time.
