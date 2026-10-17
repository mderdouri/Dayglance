# DevPi cloud station Settings trial — 2026-10-16

## Deployment

Deployed the open [PR #13](https://github.com/mderdouri/Dayglance/pull/13) station-settings-manager build to the existing production path, `/home/mderdouri/dayglance`, on DevPi (`192.168.1.91`, Raspberry Pi 3 B+, Raspberry Pi OS/Debian 13.7, arm64, 800×480 DSI touchscreen). The station-key status-label correction was deployed afterward as a follow-up commit on the same PR branch.

Updated runtime files:

| File | SHA-256 after deployment |
|---|---|
| `server.py` | `7eda32968f0941fae3041fc27215f8cab46b7184372d44204857c298d7b8d42e` |
| `app.js` | `3495aebcab47ac7a236e156dc19f9a3751ab42efd777f9ffa07a56d284775a0c` |
| `index.html` | `af9e210b6f5f360c3e8e5a76697b06198249f635e4e4d04ab848eea63f20b0c8` |
| `styles.css` | `015d3784fae40738a95804eb1d4c20ff5d2aec862f466075b5184d80db641714` |

## Device state and verification

- `dayglance.service`, `dayglance-kiosk.service`, and `devpi-blank-screen.service` are active. The forecast service restart count is 0. The kiosk was restarted once to load the Settings UI; the screensaver service was left running.
- The dashboard and `/api/station-settings` returned HTTP 200. Settings lists the existing config-defined Ambient Weather local-upload source separately from editable cloud sources.
- `config.json` remained byte-for-byte unchanged (SHA-256 `c5b52a96e8764d4bb03a973c99b406359bab1f0f0dd2f4bf3517f3ede2f71da6`). `device-settings.json` remained unchanged (SHA-256 `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`). No cloud keys or station-manager files were added on the Pi.
- Restarting the service cleared the in-memory station sample as documented. The receiver continued listening and the station's next upload arrived within its 60-second interval. The status API then reported `Receiving local uploads`, with a fresh sample.
- The local code rollback path is the exact pre-deployment `origin/main` runtime: the four deployed files' original hashes matched that revision. No Pi data/configuration backup was created because the existing device files were left untouched.
- Two synthetic 800×480 browser previews for the provider-profile and station-editor screens are in [`../screenshots/`](../screenshots/README.md). A physical DSI screenshot could not be captured: `grim` reported `failed to copy output DSI-1`. No physical-touch check was performed.

## Scope

This trial deployed PR #13 only. The separate hourly-bumper-default PR #14 was not deployed. DevPi's `config.json` explicitly retains `showBumpers: true`; that existing preference was preserved.
