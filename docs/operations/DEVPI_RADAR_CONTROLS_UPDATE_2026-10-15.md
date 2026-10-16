# DevPi Dayglance radar controls update — 2026-10-15

## User-visible changes

- Replaced the timeline slider and separate play control with two mutually toggleable range buttons: **Past 2 hours**, **Next 4 hours**, or neither.
- Both ranges play automatically only after their map tiles load. The forecast button remains available without a Rainbow key, is highlighted amber, and says **Set up**. Tapping it shows a short message pointing to **Settings → Radar & Provider Account**.
- The radar screen closes after 60 seconds without user activity. Touch, pointer, keyboard, and wheel activity reset the idle timer; automatic playback does not.
- Bumped the service-worker cache to `dayglance-shell-v10` to load the updated assets.

## Verification and deployment

- JavaScript syntax and isolated frontend tests passed (13 Node tests covering radar controls, hourly detail behavior, and air-quality presentation).
- Python server tests passed (20 tests), plus shell syntax and JSON parsing. The launcher scenario check could not run because its fixed test port 8080 is already occupied; I left that existing process untouched.
- Deployed `index.html`, `radar.js`, `styles.css`, and `sw.js` to `/home/mderdouri/dayglance` on DevPi using WSL/Ansible. SHA-256 hashes on DevPi match the local source files.
- HTTP 200 verified for the dashboard, changed assets, device-settings API, radar status, and RainViewer metadata. `dayglance.service` and `dayglance-kiosk.service` are active with zero restarts.
- `config.json` stayed at `8bb79fe16b81cba7b8fe3e47712468cac72869106f82393c91a43aa6028fff18`; `device-settings.json` stayed at `1c0d46704491ba0d67a0bd2129fecca74dd81241325b91e50a46a76bece1402c`. The saved city, device preferences, browser profile, and Rainbow credential were not modified.
- Rainbow is not configured on DevPi. Past radar remains available without it; future forecast playback requires the user to enter a key. The real touchscreen capture below shows the running dashboard after deployment; interaction with the radar controls on the physical screen has not been simulated.

![DevPi dashboard captured from the attached touchscreen after the radar controls update](../screenshots/dayglance-radar-ux-devpi-20261015.png)

Machine-readable deployment and verification evidence: [DEVPI_RADAR_CONTROLS_UPDATE_2026-10-15.json](DEVPI_RADAR_CONTROLS_UPDATE_2026-10-15.json).
