# DevPi cloud weather-station adapters — 2026-10-16

## Release

- Pull request: [#12](https://github.com/mderdouri/Dayglance/pull/12), branch `codex/station-cloud-adapters`, deployed commit `c0c7a4b8a4ad8a28f7d45de9f2d30f42dc53738f`.
- GitHub `CI / Verify` completed successfully for the PR head.
- Target verified through the `devpi` WSL/Ansible inventory alias: `192.168.1.91`, hostname `DevPi`, Debian GNU/Linux 13.7 (Trixie), arm64, kernel `6.18.50+rpt-rpi-v8`.
- Production app path: `/home/mderdouri/dayglance`; loopback URL: `http://127.0.0.1:8081/`.

## Deployment and recovery

- Replaced `server.py`, `weather_station.py`, `app.js`, and `index.html` only.
- A private rollback copy of those four prior files is retained at `/home/mderdouri/dayglance/.rollback/cloud-station-adapters-20261016` (directory mode 0700).
- `config.json` SHA-256 is unchanged: `c5b52a96e8764d4bb03a973c99b406359bab1f0f0dd2f4bf3517f3ede2f71da6`.
- `device-settings.json` SHA-256 is unchanged: `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`.
- No cloud keys or `device-station-credentials.json` were copied. Cloud polling will remain inactive until the user opts in with configuration and provider credentials. The existing local upload configuration was preserved.
- Restarted `dayglance.service` and `dayglance-kiosk.service`; `devpi-blank-screen.service` was left running. All three are active with `NRestarts=0` after deployment.

## Verification

The deployed runtime files match the PR source by SHA-256:

| File | SHA-256 |
| --- | --- |
| `server.py` | `00e050f4b11ecdde842a020b270bd76186f790f7206b417d77b9afae225b8548` |
| `weather_station.py` | `767577ee187b097c6a6e598c41cf90942bcd2b863abe2cbcac9e8779cc48c0f6` |
| `app.js` | `27c763ef2553321a660609d07ea8bd876d4ed920bc0adf2ee5854ff869d86384` |
| `index.html` | `374eef72e4c2abd0606e1334f403181e4e355eeb28ae52d02b002f9be51e983c` |

The dashboard (`/`), local station status (`/api/local-stations`), and device settings (`/api/device-settings`) returned HTTP 200 after restart. Existing settings fingerprints were checked against the pre-deployment baseline.

Local checks passed: 16 Node tests, 37 Python tests, JavaScript syntax, shell syntax, JSON validation, launcher configuration scenarios, and `git diff --check`. Provider HTTP behavior is mocked in automated tests; no provider keys were present, so live Ambient Weather or Weather Company API calls were not tested.

No touchscreen screenshot was captured: the Settings screen was not opened during this deployment, and physical touch was not tested. The visible station-source status behavior remains for user review on DevPi.
