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
    "radarIdleTimeoutSeconds": 60,
    "temperatureUnit": "fahrenheit",
    "measurementSystem": "imperial",
    "clockFormat": "system",
    "refreshMinutes": 15,
    "temperatureGraphRange": "day",
    "autoScrollLocations": false,
    "autoScrollIntervalSeconds": 30,
    "showBumpers": false
  },
  "startup": {
    "autoStart": false,
    "kiosk": true
  },
  "stationReceiver": {
    "bindAddress": "192.168.1.50",
    "port": 8082,
    "path": "/weatherstation/updateweatherstation.php"
  },
  "stationIntegrations": [
    {
      "id": "backyard",
      "name": "Backyard station",
      "provider": "ambient-weather",
      "connection": "local-upload",
      "enabled": true,
      "sourceIp": "192.168.1.60",
      "locationId": null,
      "staleAfterSeconds": 600
    }
  ]
}
```

Each configured location needs a stable, unique `id` and can provide:

- `name`: display label.
- `query` and optional `countryCode`: location text to resolve through Open-Meteo's geocoder.
- Or `latitude` and `longitude`: coordinates for a fixed location.

`defaultLocation` is the first page shown on startup. Entries in `locations` are additional pages. Set `defaultLocation` to `null` and `locations` to `[]` to require first-launch setup. After changing the file, reload Dayglance. The browser clears cached forecasts for changed configured locations and resolves them again.

Preference values are:

- `returnAfterSeconds`: `15`, `30`, `60`, `90`, `120`, `300`, or `0`; defaults to `60` seconds. Choose 15 seconds, 30 seconds, 1 minute, 1 minute 30 seconds, 2 minutes, or 5 minutes; `0` keeps the hourly view open until closed.
- `radarIdleTimeoutSeconds`: `15`, `30`, `60`, or `300`; defaults to `60` seconds (1 minute). The precipitation map closes after this much inactivity; touching, panning, zooming, or using the keyboard resets the timer.
- `temperatureUnit`: `fahrenheit` or `celsius`.
- `measurementSystem`: `imperial` or `metric`.
- `clockFormat`: `system`, `12`, or `24`.
- `refreshMinutes`: `15`, `30`, or `60`.
- `temperatureGraphRange`: `day` for the next 24 hours, `week` for a 7-day forecast, `forecast16` for up to 16 forecast days, or `history30` for 30 days of archived past-days data ending today. The history range is not a long-range forecast and is not guaranteed to be station-observed data.
- `autoScrollLocations`: `true` automatically rotates through saved locations when at least two exist; `false` leaves location changes manual. The rotation loops between saved cities and never opens the add-location page.
- `autoScrollIntervalSeconds`: `30`, `60`, `300`, or `900` seconds on each location (30 seconds, 1 minute, 5 minutes, or 15 minutes). Used only when auto-scroll is enabled.
- `showBumpers`: `false` by default to keep the hourly view uncluttered. Set to `true` to show optional left/right buttons; hourly cards remain swipeable/scrollable either way.

The temperature graph period can also be changed in **Settings → Weather & display**. The 16-day view requests the provider's maximum forecast horizon. The 30-day view requests the past 29 days plus today and displays daily highs and lows from Open-Meteo's archived past-days feature. Availability and archive coverage depend on the provider. Switching graph periods does not require a service restart.

Location rotation is configurable in **Settings → Location rotation**. It advances to the next saved location with the same smooth sideways transition as manual swiping, loops to the first location, and pauses while Settings, hourly details, or the add-location page is open. It does nothing when only one location is configured. No service restart is needed.

Hourly details for Today begin at the current local hour and hide earlier hours. If six or fewer hours remain, the view also includes up to four early hours from tomorrow. Details for another forecast day initially center the scroll position on 8 AM; the full day remains available from midnight to 11 PM. Each day starts at its own position when opened.

`startup.autoStart` enables the desktop login launcher. `startup.kiosk` selects full-screen kiosk mode (`true`) or a maximized browser window (`false`). On a local Linux or Raspberry Pi session, enabling auto-start in Settings installs the desktop login hook automatically and writes per-device overrides to `device-settings.json`; those overrides take precedence over the JSON defaults. On Raspberry Pi OS with labwc, Dayglance adds a marked entry to `~/.config/labwc/autostart`; on other Linux desktops it creates `~/.config/autostart/dayglance.desktop`. Changes apply at the next desktop login or next launcher run. `install-autostart.sh` remains available for manual or keyboard-free setup.

Browser preferences changed in the Settings menu are stored in that browser and take precedence over `config.json`. On a fresh browser profile, the JSON preferences are used directly. To switch an existing browser back to copied JSON defaults, clear Dayglance's saved site data for that browser. Keep this file free of API keys, passwords, and other secrets; the browser downloads it as a public static file.

## Local weather-station integration

Each saved city may be associated with zero or one station observation source. **Settings → Local Weather Stations** always lists the supported connection types, even before a source has been configured, and shows any configured feeds with their status; it also lets you associate a source with a saved city. The supported-source panel is informational and read-only; sources are added through `config.json`, while credentials are kept separately in the private device-only credentials file. There is no three-city cap: add an integration entry for every city/station pair, with unique source IDs; provider quotas and the one-source-per-city rule still apply. A station does not become an extra carousel location: its live measurements appear on the selected city's dashboard, while the forecast and hourly view continue to use Open-Meteo. Station values are labeled as observations and automatically stop being used when their observation timestamp is older than `staleAfterSeconds`.

Ambient Weather supports two connections:

- **Local upload:** Dayglance accepts native Ambient Weather fields and the Weather Underground-compatible upload format. Configure `stationReceiver` and `connection: "local-upload"` in `stationIntegrations`. Use reserved private LAN addresses: `bindAddress` must be the Pi's specific address (never `0.0.0.0`), and `sourceIp` must be the station's reserved address. Do not forward the listener port through the router or expose it to the public internet. Samples stay in memory and are cleared when the service restarts; the receiver ignores upload credentials and does not log upload URLs or query strings.
- **Ambient Weather cloud API:** use `connection: "cloud-api"` and the device MAC as `deviceId`. Store the user API key and application key in the untracked device-local `device-station-credentials.json` file described below. Dayglance queries the official `/v1/devices` latest-reading endpoint once per minute per credential pair. Ambient documents limits of 1 request/second per user API key and 3 requests/second per application key, so this polling interval stays below those limits. See the [Ambient API reference](https://github.com/ambient-weather/api-docs/blob/master/apiary.apib) and [Ambient API key guidance](https://ambientweather.com/faqs/question/view/id/1811/).
- **Weather Underground PWS cloud API:** use `provider: "weather-underground"`, `connection: "cloud-api"`, and the PWS `stationId`. Put the Weather Company API key in the device-local credentials file. Current API docs describe a 50,000-request/day trial limit and require an authorized API key; paid access limits and charges depend on the user's plan/agreement. Check access and terms before enabling it. See [PWS current observations](https://developer.weather.com/docs/openapi/pws-current-observations-2-0/get-v2-pws-observations-current), [authentication and quotas](https://developer.weather.com/docs/authentication), and [Getting Started/pricing](https://developer.weather.com/docs/getting-started).

Example cloud source in `config.json` (replace the example MAC and IDs):

```json
{
  "id": "cloud-backyard",
  "name": "Backyard cloud station",
  "provider": "ambient-weather",
  "connection": "cloud-api",
  "enabled": true,
  "deviceId": "00:11:22:33:44:55",
  "credentialsId": "home-account",
  "locationId": null,
  "staleAfterSeconds": 600
}
```

Example Weather Underground source:

```json
{
  "id": "wu-backyard",
  "name": "Backyard WU station",
  "provider": "weather-underground",
  "connection": "cloud-api",
  "enabled": true,
  "stationId": "KDCWASHINGTON123",
  "credentialsId": "weather-company-account",
  "locationId": null,
  "staleAfterSeconds": 600
}
```

Create `device-station-credentials.json` beside `server.py` and restrict it to the Dayglance service account (`chmod 600 device-station-credentials.json` on Linux):

```json
{
  "ambientWeatherAccounts": {
    "home-account": {
      "apiKey": "PASTE_USER_API_KEY_HERE",
      "applicationKey": "PASTE_APPLICATION_KEY_HERE"
    }
  },
  "weatherUndergroundAccounts": {
    "weather-company-account": {
      "apiKey": "PASTE_WEATHER_COMPANY_API_KEY_HERE"
    }
  }
}
```

This credential file is ignored by Git and is never served to the browser. Keep it on the device only and do not paste keys into chat. Ambient requires both keys; the official API limits requests to 1 per second per user key and 3 per second per application key. The cloud poller requests the latest reading once per minute per credential pair and reuses the response for all configured devices using those keys.

Weathercloud's [official FAQ](https://weathercloud.net/en/faq) says it currently has no API for retrieving station data. Its API is for uploads; use a station's direct local upload to Dayglance when supported rather than scraping the Weathercloud website.

In the station's companion app, look for a custom server/custom upload option and enter the Pi's LAN address, HTTP, port, upload path, and either the Ambient Weather or Weather Underground-compatible protocol. Ambient's official WS-2902 family FAQ documents a custom server form and both protocol formats, but the option and fields vary by station revision and firmware. Check the [Ambient WS-2902 FAQ](https://ambientweather.com/faqs/question/tags/tag/WS-2902A/) and your exact console manual; the listing for the device used during Dayglance development appears to be in this family, but its installed revision/firmware has not been verified. Reserve the station address in the router before enabling the listener. Once `config.json` is updated, restart the Dayglance service. Assign that station to its city under Settings; changing this association takes effect immediately and is saved in the browser on that device.

Both cloud adapters use the same one-station-per-city rule, with credentials held in a restricted server-side device file rather than `config.json` or browser storage.

See [Local weather stations](LOCAL_STATIONS.md) for the complete setup, network safety, data mapping, and troubleshooting guide.

## Runtime storage and writes

While the page is open, fetched forecasts and 30-day history are kept in memory. They are no longer written to browser storage on every refresh. Locations, preferences, and geocoded coordinates remain saved so the display can be restored across restarts. After a browser restart, Dayglance fetches weather again; without a network connection it cannot show a forecast left over from a previous session. Existing saved forecast/history caches are removed from persistent browser storage on the first save after this update, while remaining available in memory until the page closes.

The service worker keeps the app shell for offline startup. It revalidates those files from the local server and only updates its cache when a file's content changes; it does not cache API responses. The Python server now logs failed HTTP requests rather than every successful asset/settings request. Raspberry Pi startup options are written to `device-settings.json` only when changed in Settings.

## Settings menu

Use the gear button beside refresh to edit the default location, add or remove additional locations, and adjust forecast and hourly-view preferences. Swipe or drag the hourly cards directly to explore the forecast; optional left and right buttons can move through the same content. Removing a location loaded from `config.json` hides it only on that device; remove it from the file to remove it from every copy. Startup controls are available when the app is running from its local Python server on the Pi and the desktop auto-start entry has been installed. Startup options apply the next time the Dayglance launcher runs; they do not restart an open display or require a forecast-server restart.

The hourly view return timer and precipitation-map idle timeout are both adjustable immediately in Settings and can be preconfigured in `config.json`. The hourly timer defaults to one minute and supports 15 seconds through 5 minutes, or can be set to stay open until closed. The precipitation-map timer defaults to one minute and supports 15 seconds, 30 seconds, 1 minute, or 5 minutes. A local 800×480 settings preview is shown below.

![Dayglance settings at 800×480, showing the hourly view return timer set to one minute](../screenshots/dayglance-hourly-timeout-settings-20261016.png)
