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

Do not put a user's location configuration in Git or in an unencrypted backup. Before replacing an installation or moving its configuration, preserve required configuration/state using the Pi project's encrypted backup and restore procedure. Keep a known-good application build available so code can be rolled back without restoring or overwriting user settings.

## Raspberry Pi example

For an existing kiosk installation, keep its current application directory, local URL and port, Chromium profile, `config.json`, and `device-settings.json`. Replace only the explicitly listed application assets and restart the existing user services. The actual paths and profile name vary by device.

The current server stores the two JSON files inside the application directory. A future improvement would move Pi-local configuration to a stable XDG config directory outside versioned releases, with a one-time migration and backward-compatible fallback. Until that migration exists, an in-place allowlist update is required to protect file-based settings.

