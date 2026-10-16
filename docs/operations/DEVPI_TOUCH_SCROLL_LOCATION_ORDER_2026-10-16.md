# DevPi touchscreen and location-order trial — 2026-10-16

## Deployment

Deployed the combined PR #8 and PR #9 trial build to the normal Dayglance service at `http://127.0.0.1:8081/` on DevPi (`192.168.1.91`). The build contains hourly and rain-map timeout controls, radar updates, touch-first scrolling with no visible scrollbars, swipeable location autocomplete, and saved-location ordering/default selection.

The deployment updated `index.html`, `app.js`, `styles.css`, `sw.js`, `radar.js`, `location-order.js`, and `server.py`. SHA-256 values for all seven files matched the reviewed source. The private rollback copy is `/home/mderdouri/dayglance/.rollback/pr8-pr9-20261016` (directory mode `0700`); the pre-existing runtime copies were retained there.

The user's `config.json` and `device-settings.json` stayed unchanged, confirmed by matching before/after SHA-256 fingerprints. No browser profile, saved browser locations, app preferences, Rainbow key, startup settings, blank-screen settings, or OS packages were changed. The normal `dayglance.service` and `dayglance-kiosk.service` were restarted to load the code; both and `devpi-blank-screen.service` are active with `NRestarts=0`. No reboot was performed.

During verification, the newly added `location-order.js` initially returned HTTP 404 because the Python server has an explicit static-file allowlist. Added the file to that allowlist and added a regression test, then redeployed `server.py`, restarted the service and kiosk, and confirmed the helper now returns HTTP 200. This was corrected before the deployment was marked complete.

## Verification

- DevPi served HTTP 200 for `/`, `/index.html`, `/app.js`, `/styles.css`, `/sw.js`, `/radar.js`, `/location-order.js`, and `/api/device-settings` after restart.
- The installed SHA-256 values matched the local deployment build.
- Preserved configuration fingerprints: `config.json` `8bb79fe16b81cba7b8fe3e47712468cac72869106f82393c91a43aa6028fff18`; `device-settings.json` `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`.
- Local 800×480 headless Chrome smoke test passed Settings and autocomplete touch swipes, mouse-like drags, wheel input, keyboard paging, scrolling to the end, hidden scrollbars, suggestion selection, default/order persistence across reload, and hourly horizontal touch/wheel scrolling.
- 23 JavaScript tests, 21 Python tests, launcher scenarios, shell syntax, JSON parsing, and `git diff --check` passed.
- The settings screenshot is [dayglance-location-order-settings-20261016.png](../screenshots/dayglance-location-order-settings-20261016.png).

Browser simulation is not a physical-touch test. The actual DevPi panel swipe and screensaver wake/resume have not been retested in this deployment.

## Pull requests

- [PR #8 — precipitation radar and configurable timeouts](https://github.com/mderdouri/Dayglance/pull/8): open; GitHub Verify check passed.
- [PR #9 — touchscreen scrolling and location management](https://github.com/mderdouri/Dayglance/pull/9): open and stacked on PR #8; local checks passed. GitHub CI is configured for pull requests targeting `main`, so it will run after PR #8 merges and PR #9 is retargeted to `main`.

Machine-readable details: [DEVPI_TOUCH_SCROLL_LOCATION_ORDER_2026-10-16.json](DEVPI_TOUCH_SCROLL_LOCATION_ORDER_2026-10-16.json).
