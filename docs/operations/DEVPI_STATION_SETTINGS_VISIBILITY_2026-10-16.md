# DevPi station connection Settings visibility — 2026-10-16

## Release

- Pull request: [#12](https://github.com/mderdouri/Dayglance/pull/12), branch `codex/station-cloud-adapters`, follow-up commit `f60840c`.
- Target verified by WSL/Ansible: `192.168.1.91`, hostname `DevPi`; production app path `/home/mderdouri/dayglance`, loopback URL `http://127.0.0.1:8081/`.
- Settings now always lists Ambient Weather local upload/cloud API and Weather Underground PWS cloud API, including when no station source is configured. It explains where to define sources and where to keep private provider credentials.

## Deployment and recovery

- Deployed `index.html`, `app.js`, and `styles.css`; restarted only `dayglance-kiosk.service`.
- Pre-deployment copies are retained in `/home/mderdouri/dayglance/.rollback/station-settings-visibility-20261016` with directory mode 0700.
- The existing `config.json` SHA-256 remains `c5b52a96e8764d4bb03a973c99b406359bab1f0f0dd2f4bf3517f3ede2f71da6`; `device-settings.json` remains `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`.
- No station configuration, credentials, browser preferences, or saved locations were changed.

## Verification and limits

- Local source and deployed SHA-256 values match:

| File | SHA-256 |
| --- | --- |
| `index.html` | `d5d720783cd0311369dcbdd2d7ac8e16a01981cf930bf271e175c68583fed521` |
| `app.js` | `16bc3dfc3b23bf3026d5016d5bbc5c1bb379a2d721d4dbc00bece755e8bde283` |
| `styles.css` | `296a4c465041cd58d5a05c1d23b87590fa4eacd4cd308fb39a0fb945731d33a3` |
- The dashboard returned HTTP 200 and the served HTML, JS, and CSS each contained the expected new Settings content. `dayglance.service`, `dayglance-kiosk.service`, and `devpi-blank-screen.service` are active with `NRestarts=0`.
- Local checks passed: seven radar Node tests, 38 Python tests, JavaScript syntax, shell syntax, JSON validation, launcher scenarios, and `git diff --check`.
- An isolated headless Chrome capture at 800×480 shows the Settings screen from the current app markup and styles; it is a simulated preview, not a capture from the physical touchscreen. The screenshot is [`dayglance-station-connections-settings-20261016.png`](../screenshots/dayglance-station-connections-settings-20261016.png).
- Physical touchscreen interaction, cloud API credentials, and live provider polling were not tested. Sources remain config-file based; the Settings page provides the discoverable provider list, status, city association, and activation instructions.
