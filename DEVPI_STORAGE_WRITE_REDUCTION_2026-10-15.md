# DevPi storage-write reduction — 2026-10-15

## Changes

Dayglance now retains fetched forecast and 30-day history responses in memory rather than persisting each refreshed response to browser local storage. Location definitions, preferences, and resolved coordinates still persist. Existing saved forecast/history caches are removed from persistent browser storage on the first save after this build loads; an already-loaded copy remains usable in memory until the page closes. After a browser restart, weather is fetched again, so a network connection is needed for fresh forecast data.

The service worker now caches only the local app shell. API paths bypass it. It revalidates shell resources against the local server and writes a cached body only when content differs. The Python server suppresses successful request log entries and still logs errors. Device startup settings remain written only when changed through Settings.

## DevPi deployment and verification

- Target: `devpi` (`192.168.1.91`), app path `/home/mderdouri/dayglance-preview`, server `127.0.0.1:8081`.
- Updated five changed runtime files: `index.html`, `app.js`, `styles.css`, `sw.js`, and `server.py`. `config.json` and `manifest.webmanifest` already matched and were not copied.
- Restarted `weather-preview.service` to load the server logging change and `weather-kiosk-preview.service` to load the new app/service worker. The existing Chromium profile and device settings file were left in place. No reboot or startup option was changed.
- SHA-256 of all seven served files matched the local source after deployment.
- HTTP 200 confirmed for `/`, `/app.js`, `/styles.css`, `/config.json`, `/manifest.webmanifest`, `/sw.js`, and `/api/device-settings`.
- `weather-preview.service`, `weather-kiosk-preview.service`, and `devpi-blank-screen.service` were active; each reported `NRestarts=0`. The app directory remained `0755 mderdouri:mderdouri`.
- Local checks: six Python server tests passed; `node --check app.js`, `node --check sw.js`, JSON validation, and `git diff --check` passed. A Node service-worker simulation verified unchanged shell content causes no cache write, API requests bypass the worker, changed shell content causes one write, and offline fallback serves the cached shell.

## Write-frequency assessment and limits

Source-path analysis found forecast refreshes (default 15 minutes per active location) and history requests previously called `localStorage.setItem` even though they were transient. They now remain in RAM and are not part of durable state serialization. Identical durable state is also not rewritten. Shell files may be written on first install or content change; unchanged shell loads do not write. API responses are not cached. Normal successful HTTP requests no longer add server journal lines; failures remain logged. Device settings are saved only when a startup setting changes.

These rates are based on code-path inspection and a simulated service-worker test, not a measured SD-card write counter or kernel block-I/O trace. The storage change is non-visual; after the user confirmed the display was awake, a live 800×480 dashboard screenshot was captured at `docs/images/dayglance-devpi-20261015.png` and copied to the project root. Physical touchscreen and screensaver wake/resume were not exercised during this deployment.

## Operational validation note

Two early local probes were discarded: Windows PowerShell did not provide the `python` command alias, and a shell-quoted HTTP loop expanded its variables incorrectly. JavaScript syntax and JSON checks were rerun with native Node/WSL Python, and each remote endpoint was then checked independently with Ansible's URI module; those corrected checks passed.

A Node simulation of the actual save() function also passed: it removed legacy forecast/history fields from durable storage once, retained location/preferences, and performed no later storage write when only forecast/history data changed. Its first harness attempt lacked the app's STORE_KEY constant and was discarded; the corrected harness passed.

Before the change, a single actively displayed location refreshed every 15 minutes by default and each successful forecast called localStorage.setItem, so the expected steady-state was about four persistent-storage write calls per hour for one location, plus an initial fetch. Visiting or auto-rotating to other cities could add a write on each successful city fetch. A history request could also write when first fetched or refreshed after its six-hour cache age. These are application write calls inferred from source, not measured SD-card flushes; browser storage implementations may buffer or coalesce physical I/O. After the change, ordinary weather/history refreshes make zero persistent browser-storage write calls, except the one-time cleanup of legacy caches at first save.

