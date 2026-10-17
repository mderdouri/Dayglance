# DevPi Dayglance PR #16 deployment — 2026-10-17

## Release

- Pull request #16, “Reorganize Settings and add U.S. severe weather alerts,” is merged to `main`.
- Deployed merged commit: `406207117172859cfb109b86045eb7f4dccf3fa0`.
- Target: DevPi (`192.168.1.91`), Raspberry Pi 3 B+, Raspberry Pi OS/Debian 13.7 Trixie, arm64, 800×480 touchscreen.
- Production app path: `/home/mderdouri/dayglance`; loopback URL: `http://127.0.0.1:8081/`.

## Deployment and recovery

- Updated only `app.js`, `index.html`, `radar.js`, `server.py`, and `styles.css`.
- A private rollback copy of the previous versions is retained at `/home/mderdouri/dayglance/.rollback/pr16-severe-alerts-20261017` (directory mode 0700; files mode 0600).
- `config.json` remained unchanged: SHA-256 `c5b52a96e8764d4bb03a973c99b406359bab1f0f0dd2f4bf3517f3ede2f71da6`.
- `device-settings.json` remained unchanged: SHA-256 `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`.
- Existing Chromium profile, browser storage, app origin, saved locations, user preferences, local weather-station configuration, and credentials were not copied or modified.
- Restarted `dayglance.service` and `dayglance-kiosk.service` to load the server and UI changes. `devpi-blank-screen.service` remained active.

## Verification

Deployed runtime SHA-256 values match the merged source:

| File | SHA-256 |
|---|---|
| `app.js` | `bc370aa83e95a6d46b5b00ac93d5125134140b9a7c981c44cb33e3211ab6faa3` |
| `index.html` | `cd3f141e9bc6184130283e8fca6b6ac4c0046336a5cbe72eddc201779a0eb7e3` |
| `radar.js` | `3b99823ebfe922f07091ddce724e03bf961359e9269e5da9fa62b92096700b20` |
| `server.py` | `cbdc0013bddf9a0b724e4716f5ffd5426920bccb553a5f07ddd8f5128f2e2fa4` |
| `styles.css` | `0ef7497d497e6667d8ae8ed17da16237bb9476cb4beb40d23e47bbf6f2adb31b` |

- The dashboard, `index.html`, `app.js`, `radar.js`, `styles.css`, `/api/device-settings`, and `/api/local-stations` returned HTTP 200.
- The served page contains the Severe Weather Alerts view and the Connections & Alerts settings entry.
- The local weather-station receiver returned to “Receiving local uploads” after the expected in-memory sample reset on server restart.
- `dayglance.service`, `dayglance-kiosk.service`, and `devpi-blank-screen.service` are active; all report `NRestarts=0`.
- Before deployment, Ansible SSH preflight confirmed hostname `DevPi`, account `mderdouri`, and active service state. The playbook syntax check and deployment completed without unreachable or failed tasks.
- GitHub Actions CI Verify passed for PR #16. PR checks: 52 Python tests, 16 JavaScript tests, JavaScript syntax, shell syntax, configuration JSON, launcher checks, and diff whitespace checks passed.
- The PR includes four isolated 800×480 preview screenshots with synthetic alert data in `docs/screenshots/`. No physical-panel screenshot or physical-touch test was taken in this deployment.

## Evidence

- [PR #16](https://github.com/mderdouri/Dayglance/pull/16)
- [Configuration and feature documentation](docs/guides/CONFIGURATION.md)
- [Screenshot gallery](docs/screenshots/README.md)
- Previous code retained on DevPi in the rollback directory above.
