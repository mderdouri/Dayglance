# DevPi Settings layout deployment — PR #18 — 2026-10-17

## Change

Deployed PR #18 commit `886effa779c40736d15fef5f50d1e4d6cf7be622` to the normal Dayglance service on DevPi (`192.168.1.91`, `/home/mderdouri/dayglance`, loopback port 8081). Updated only `index.html` and `styles.css`; the Connections & Alerts card now appears first and spans the Settings width, with Locations below and the remaining cards paired by category. The narrow layout stacks those groups in the same order.

Ansible retained the replaced assets in `/home/mderdouri/dayglance/.rollback/pr18-settings-layout-20261017` (directory mode 0700; files mode 0600). It restarted `dayglance-kiosk.service` to load the new assets. The forecast server was not restarted and the Pi was not rebooted.

## Verification

- CI run 41 passed; local verification passed 16 JavaScript tests, 52 Python tests, shell syntax and launcher checks, JSON validation, and `git diff --check`.
- Isolated browser simulation at 800×480 confirmed the order and widths; at 600×800 the cards stack in that order. Simulated touch swipe, mouse drag, wheel, and keyboard Page Down all scrolled; Connections & Alerts opened and returned to Settings, and the close control worked. This was not a physical touchscreen test.
- DevPi-served `index.html` and `styles.css` returned HTTP 200 and match the deployed commit SHA-256 values. `/api/device-settings` returned HTTP 200.
- `dayglance.service`, `dayglance-kiosk.service`, and `devpi-blank-screen.service` are active with `NRestarts=0` after deployment.
- `config.json` SHA-256 stayed `c5b52a96e8764d4bb03a973c99b406359bab1f0f0dd2f4bf3517f3ede2f71da6`; `device-settings.json` stayed `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`. No app settings, location data, browser profile, or screensaver configuration was changed.

## Rollback

Restore `index.html` and `styles.css` from `.rollback/pr18-settings-layout-20261017` to `/home/mderdouri/dayglance/`, then restart `dayglance-kiosk.service`. The forecast server does not need a restart for these static assets.
