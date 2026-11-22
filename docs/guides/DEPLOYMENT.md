# Updating an existing Dayglance installation

Dayglance settings live in more than one place. Preserve each store when updating an existing installation:

| Setting or state | Stored in | Update guidance |
|---|---|---|
| File-defined locations, preferences, and startup defaults | `config.json` in the installation directory | Treat this as user configuration on a Pi. Keep the existing file when copying a new build. |
| Pi-local startup overrides | `device-settings.json` in the installation directory | Keep the existing file. The server creates it with owner-only permissions when settings are changed in the UI. |
| Locations and preferences changed in the browser | Browser local storage | Keep the same browser profile and app origin; do not clear site data. |
| Chromium cookies, site data, and profile state | Chromium's user-data directory | Keep the existing directory and launch option. |

## Routine update procedure

1. Update the existing installation in place. Copy only the application assets that changed; do not remove or replace the whole installation directory.
2. Leave `config.json` and `device-settings.json` on the device. Do not copy the repository's example `config.json` over a user's file.
3. Keep the same app origin (scheme, host, and port) and Chromium user-data directory. Browser local storage belongs to both; changing either can make saved browser settings appear to be gone.
4. Restart the Dayglance server when its Python code changes. Restart or reload the kiosk browser when its HTML, JavaScript, CSS, or service worker changes, while reusing the same Chromium profile.
5. Verify that the app still opens the saved place and that its units, graph period, and other preferences are still selected. Check the startup controls on the Pi as well.

## Kiosk and screensaver verification

When the effective startup setting enables full-screen kiosk mode, verify the running display rather than relying on the saved setting, an active service, or a `--kiosk` launch flag alone:

1. Read the Pi-local startup override and the `config.json` startup default without changing either. The Pi-local override takes precedence. Respect windowed mode if kiosk mode is disabled.
2. Query or restart the user-scoped kiosk browser service from the logged-in graphical session, using that session's `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS`. A systemd user-service check run outside that session can report a misleading inactive state.
3. If kiosk mode is enabled and the kiosk browser service is already running, restart only that service to ensure a fresh Chromium window receives the launch setting. Keep the existing browser profile, app origin, and user data. Do not enable auto-start or restart the forecast server or screensaver service unless the changed application code requires it.
4. Capture the actual display after launch. Confirm the dashboard fills the screen and the browser tabs, address bar, and desktop panels are hidden. A healthy service, successful HTTP request, or launch flag is supporting evidence, not a substitute for this screen check.
5. Confirm the dashboard's saved theme and user preferences remain present. Let the operating system's normal screensaver continue to work; do not disable or restart it to make the screenshot look correct.
6. Verify a normal screensaver wake when practical. If that requires a physical touch, have the device user perform it and then inspect the screen again. Report the wake check separately; do not claim it passed if only the post-launch screen was captured.

Do not put a user's location configuration in Git or in an unencrypted backup. Before replacing an installation or moving its configuration, preserve required configuration/state using the Pi project's encrypted backup and restore procedure. Keep a known-good application build available so code can be rolled back without restoring or overwriting user settings.

## Raspberry Pi example

For an existing kiosk installation, keep its current application directory, local URL and port, Chromium profile, `config.json`, and `device-settings.json`. Replace only the explicitly listed application assets and restart the existing user services. The actual paths and profile name vary by device.

The current server stores the two JSON files inside the application directory. A future improvement would move Pi-local configuration to a stable XDG config directory outside versioned releases, with a one-time migration and backward-compatible fallback. Until that migration exists, an in-place allowlist update is required to protect file-based settings.
