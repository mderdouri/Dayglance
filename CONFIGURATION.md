# Configuration

Dayglance can be configured either by editing `config.json` before launch or through its on-screen Settings menu. The JSON file is the supported copy-and-deploy path for keyboard-free installations.

Configuration sources are combined in this order:

- `config.json` is a project-level file for locations an administrator wants preloaded on every browser using this copy.
- Browser-saved location edits and display preferences override the corresponding JSON defaults in that browser profile.
- Raspberry Pi startup options in `device-settings.json` (ignored by Git) override the `startup` defaults in `config.json`. The Settings menu writes this device-local file.

## First launch

The checked-in `config.json` intentionally has no preset location. A new browser therefore opens the location setup screen and asks the user to search for a city or ZIP/postal code. Suggestions are checked as the user types; choose the matching result to confirm it.

## Preconfigure a default location

Edit or copy `config.json` into the project root before starting Dayglance. Its `_documentation` section describes valid inputs and gives examples; Dayglance ignores that section. The file supports default and additional locations, every current display preference, and startup options:

```json
{
  "defaultLocation": {
    "id": "home",
    "name": "San Francisco, California",
    "query": "San Francisco",
    "countryCode": "US"
  },
  "locations": [
    {
      "id": "work",
      "name": "Oakland, California",
      "query": "Oakland",
      "countryCode": "US"
    }
  ],
  "preferences": {
    "returnAfterSeconds": 60,
    "temperatureUnit": "fahrenheit",
    "measurementSystem": "imperial",
    "clockFormat": "system",
    "refreshMinutes": 15,
    "temperatureGraphRange": "day",
    "autoScrollLocations": false,
    "autoScrollIntervalSeconds": 30,
    "showBumpers": true
  },
  "startup": {
    "autoStart": false,
    "kiosk": true
  }
}
```

Each configured location needs a stable, unique `id` and can provide:

- `name`: display label.
- `query` and optional `countryCode`: location text to resolve through Open-Meteo's geocoder.
- Or `latitude` and `longitude`: coordinates for a fixed location.

`defaultLocation` is the first page shown on startup. Entries in `locations` are additional pages. Set `defaultLocation` to `null` and `locations` to `[]` to require first-launch setup. After changing the file, reload Dayglance. The browser clears cached forecasts for changed configured locations and resolves them again.

Preference values are:

- `returnAfterSeconds`: `0`, `30`, `60`, `90`, or `120`; defaults to `60` seconds, and `0` keeps the hourly view open until closed.
- `temperatureUnit`: `fahrenheit` or `celsius`.
- `measurementSystem`: `imperial` or `metric`.
- `clockFormat`: `system`, `12`, or `24`.
- `refreshMinutes`: `15`, `30`, or `60`.
- `temperatureGraphRange`: `day` for the next 24 hours, `week` for a 7-day forecast, `forecast16` for up to 16 forecast days, or `history30` for 30 days of archived past-days data ending today. The history range is not a long-range forecast and is not guaranteed to be station-observed data.
- `autoScrollLocations`: `true` automatically rotates through saved locations when at least two exist; `false` leaves location changes manual. The rotation loops between saved cities and never opens the add-location page.
- `autoScrollIntervalSeconds`: `30`, `60`, `300`, or `900` seconds on each location (30 seconds, 1 minute, 5 minutes, or 15 minutes). Used only when auto-scroll is enabled.
- `showBumpers`: `true` to show the optional hourly left/right buttons, or `false` to hide them. Hourly cards remain swipeable/scrollable either way.

The temperature graph period can also be changed in **Settings → Weather & display**. The 16-day view requests the provider's maximum forecast horizon. The 30-day view requests the past 29 days plus today and displays daily highs and lows from Open-Meteo's archived past-days feature. Availability and archive coverage depend on the provider. Switching graph periods does not require a service restart.

Location rotation is configurable in **Settings → Location rotation**. It advances to the next saved location with the same smooth sideways transition as manual swiping, loops to the first location, and pauses while Settings, hourly details, or the add-location page is open. It does nothing when only one location is configured. No service restart is needed.

`startup.autoStart` enables the desktop login launcher after `install-autostart.sh` has installed it. `startup.kiosk` selects full-screen kiosk mode (`true`) or a maximized browser window (`false`). These values are read by the launcher on its next run. The app's Settings menu can change them on the Pi; those per-device changes are written to `device-settings.json` and take precedence over the JSON defaults.

Browser preferences changed in the Settings menu are stored in that browser and take precedence over `config.json`. On a fresh browser profile, the JSON preferences are used directly. To switch an existing browser back to copied JSON defaults, clear Dayglance's saved site data for that browser. Keep this file free of API keys, passwords, and other secrets; the browser downloads it as a public static file.

## Runtime storage and writes

While the page is open, fetched forecasts and 30-day history are kept in memory. They are no longer written to browser storage on every refresh. Locations, preferences, and geocoded coordinates remain saved so the display can be restored across restarts. After a browser restart, Dayglance fetches weather again; without a network connection it cannot show a forecast left over from a previous session. Existing saved forecast/history caches are removed from persistent browser storage on the first save after this update, while remaining available in memory until the page closes.

The service worker keeps the app shell for offline startup. It revalidates those files from the local server and only updates its cache when a file's content changes; it does not cache API responses. The Python server now logs failed HTTP requests rather than every successful asset/settings request. Raspberry Pi startup options are written to `device-settings.json` only when changed in Settings.

## Settings menu

Use the gear button beside refresh to edit the default location, add or remove additional locations, and adjust forecast and hourly-view preferences. Swipe or drag the hourly cards directly to explore the forecast; optional left and right buttons can move through the same content. Removing a location loaded from `config.json` hides it only on that device; remove it from the file to remove it from every copy. Startup controls are available when the app is running from its local Python server on the Pi and the desktop auto-start entry has been installed. Startup options apply the next time the Dayglance launcher runs; they do not restart an open display or require a forecast-server restart.
