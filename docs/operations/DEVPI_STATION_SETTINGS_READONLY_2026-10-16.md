# DevPi station Settings clarity and multi-city support — 2026-10-16

## Release

- Pull request: [#12](https://github.com/mderdouri/Dayglance/pull/12), branch `codex/station-cloud-adapters`, code commit `b5a4e3e`.
- Target verified by WSL/Ansible: `192.168.1.91`, hostname `DevPi`; production path `/home/mderdouri/dayglance`.
- Settings now labels the source list “Config file · read-only” and states the provider types are references, not input fields. The types are shown in a flat gray panel rather than field-like white cards.
- There is no three-city integration cap in the configuration validator. Regression coverage confirms four unique local station sources can be assigned to four different city IDs. A city still supports at most one station source.

## Deployment and recovery

- Deployed `index.html` and `styles.css`; restarted only `dayglance-kiosk.service`.
- Previous files are retained at `/home/mderdouri/dayglance/.rollback/station-settings-readonly-20261016` (directory mode 0700).
- `config.json` SHA-256 stayed `c5b52a96e8764d4bb03a973c99b406359bab1f0f0dd2f4bf3517f3ede2f71da6`; `device-settings.json` stayed `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`.
- No provider sources or credentials were added; browser settings and saved locations were preserved.

## Verification and limits

- Local and deployed hashes match:

| File | SHA-256 |
| --- | --- |
| `index.html` | `1db0db3918082723e0e8c9e8e7c23b16d6b5c013b7f8c9257fb7aa36c7b9f873` |
| `styles.css` | `139ec4ef54a58a092733daed6a07041a5e7018a24a1b98c6bc9b17639a2b6565` |
- Dashboard returned HTTP 200; the served HTML contains the read-only label and clarification. `dayglance.service`, `dayglance-kiosk.service`, and `devpi-blank-screen.service` are active with `NRestarts=0`.
- Checks passed: 16 Node tests, 39 Python tests, JS syntax, shell syntax, JSON validation, launcher scenarios, and `git diff --check`.
- The updated 800×480 screenshot is an isolated Chrome preview, not a physical touchscreen capture: [`dayglance-station-connections-settings-20261016.png`](../screenshots/dayglance-station-connections-settings-20261016.png).
- Physical multi-station uploads, cloud polling, and touch interaction were not exercised in this deployment.
