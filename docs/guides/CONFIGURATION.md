# Configuration

Dayglance can be configured either by editing `config.json` before launch or through its on-screen Settings menu. The JSON file is the supported copy-and-deploy path for keyboard-free installations.

Configuration sources are combined in this order:

- `config.json` is a project-level file for locations an administrator wants preloaded on every browser using this copy.
- Browser-saved location edits and display preferences override the corresponding JSON defaults in that browser profile.
- Raspberry Pi startup options in `device-settings.json` (ignored by Git) override the `startup` defaults in `config.json`. The Settings menu writes this device-local file.
- Cloud station definitions and provider keys managed in **Settings → Local Weather Stations** are stored on the Pi in ignored `device-station-settings.json` and `device-station-credentials.json`. These files never replace `config.json`; cloud station additions apply live.

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
    "showBumpers": false,
    "alertsEnabled": true,
    "alertMinimumSeverity": "moderate"
  },
  "startup": {
    "autoStart": false,
    "kiosk": true
  },
  "stationReceiver": {
    "bindAddress": "10.254.254.50",
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
      "sourceIp": "10.254.254.60",
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
- `alertsEnabled`: `true` (default) to show active U.S. National Weather Service alerts for the currently displayed city; `false` disables the alert banner and alert checks.
- `alertMinimumSeverity`: `minor`, `moderate` (default), `severe`, or `extreme`. Alerts at or above the selected severity are shown. Alerts without a reported severity remain visible so missing metadata cannot silently hide them.

## Severe weather alerts

Dayglance uses the free [National Weather Service active alerts API](https://www.weather.gov/documentation/services-web-alerts) for U.S. locations. It checks the currently displayed city every five minutes, keeps results in memory, and shows an alert banner on that city's dashboard when an alert meets the configured severity. Tap the banner for the alert headline, area, urgency, effective/expiration times, description, and instructions. A newly received alert visible under the selected severity filter briefly wakes a supported idle display, opens its details, and restarts the normal inactivity countdown. Alerts without severity metadata remain visible and can also wake the display. Repeated updates to the same alert do not wake the display again. This works with Linux X11 screensavers and Wayland sessions managed by a running `swayidle` user service; other display managers may not support programmatic wake. Manage the feature in **Settings → Connections & Alerts → Severe Weather Alerts** or set `preferences.alertsEnabled` and `preferences.alertMinimumSeverity` in `config.json`. No API key or service restart is needed. Locations outside the U.S. show an unsupported status. Dayglance is a display-only supplement, not an emergency alert system or push notification service; keep official alerts enabled on your phone or NOAA Weather Radio.

### Future international alert coverage

Severe weather alerts currently work only for U.S. locations through the National Weather Service. International sources are documented for future evaluation in [Dayglance issue #15](https://github.com/mderdouri/Dayglance/issues/15); they are not active in the app yet.

Research found public alert feeds or services for these requested countries. Most regional feeds use the Common Alerting Protocol (CAP), RSS, or Atom rather than one shared worldwide API.

| Country or group | Public source identified | Integration note |
|---|---|---|
| Canada | Environment and Climate Change Canada Meteorological Service GeoMet weather-alert collection | Public OGC API with geospatial alert fields. |
| Mexico | CONAGUA / National Meteorological Service (SMN) | CAP feed listed by the WMO. |
| France, United Kingdom, Belgium, Portugal, Italy, Greece | MeteoAlarm country Atom feeds | Public feeds are available. Direct API access for redistributors may require requesting a token. |
| Germany | Deutscher Wetterdienst (DWD) | Official alert feed listed by the WMO. |
| India | India Meteorological Department and National Disaster Management Authority / Sachet | Public CAP feeds listed by the WMO. |
| China | China Meteorological Administration | Public CAP feed listed by the WMO. |
| Japan | Japan Meteorological Agency disaster-prevention XML Atom feeds | Needs a country-specific XML and warning-area adapter. JMA says feeds can be delayed or interrupted. |
| Algeria | Office National de la Météorologie | CAP feed listed by the WMO. |
| Tunisia | National Institute of Meteorology (INM) | CAP feed listed by the WMO. |
| Egypt | Egyptian Meteorological Authority | CAP feed listed by the WMO. |
| Saudi Arabia | National Center for Meteorology | Official CAP-alert source listed by the WMO; endpoint format needs validation during implementation. |
| Pakistan | Pakistan Meteorological Department (PMD) WIS 2.0 | Public CAP-alert dataset is published through its WIS 2.0 service; validate the message/query interface. |
| Bangladesh | Bangladesh Meteorological Department (BMD) | Public CAP alert pages are available; a stable public feed/API contract still needs confirmation. |
| Burkina Faso | National Meteorological Agency (ANAM) | CAP feed listed by the WMO. |
| Senegal | National Agency of Civil Aviation and Meteorology (ANACIM) | CAP feed listed by the WMO. |
| South Africa | South African Weather Service | CAP RSS feed listed by the WMO. |
| Spain | State Meteorological Agency (AEMET) | CAP RSS feed listed by the WMO. |

Sources: [WMO Severe Weather Information Centre source registry](https://severeweather.wmo.int/json/sources.json), [MeteoAlarm API portal](https://api.meteoalarm.org/) and [active feed directory](https://feeds.meteoalarm.org/), [Canada GeoMet alert fields](https://api.weather.gc.ca/collections/weather-alerts/queryables?f=html), [JMA XML feed information](https://xml.kishou.go.jp/xmlpull.html), [Pakistan PMD WIS 2.0](https://wis2box.pmd.gov.pk/), and [Bangladesh BMD CAP alerts](https://cap.bmd.gov.bd/bmd-cap-alerts/).

The WMO registry reports feed availability, not an uptime guarantee. Public access alone does not grant unrestricted redistribution rights. Before adding any provider, verify its license and attribution, rate limits, update cadence, geographic matching method, supported warning types, and failure behavior. In particular, a country-wide alert feed must not be treated as a city-specific warning unless its area geometry or official warning-area identifiers support that match. International coverage remains a future feature; NWS is the only implemented alert provider for now.

Settings keeps **Locations** at the top, followed by day-to-day **Weather & Display**, **Startup & Screen**, and compact location/hourly controls. Select **Connections & Alerts** to manage local/cloud station integrations, radar accounts and provider-health indicators, and severe weather alert preferences. The status dots summarize recent checks: green means recently healthy, amber means waiting, stale, or recovering, red means an observed failure, and gray means not configured or with no status available yet.

![Settings for severe weather alerts, including the minimum-severity selector and feed status](../screenshots/dayglance-connections-alerts-20261016.png)

This isolated preview uses synthetic alert data for display verification; it is not a physical Pi capture or live warning.

The temperature graph period can also be changed in **Settings → Weather & display**. The 16-day view requests the provider's maximum forecast horizon. The 30-day view requests the past 29 days plus today and displays daily highs and lows from Open-Meteo's archived past-days feature. Availability and archive coverage depend on the provider. Switching graph periods does not require a service restart.

Location rotation is configurable in **Settings → Location rotation**. It advances to the next saved location with the same smooth sideways transition as manual swiping, loops to the first location, and pauses while Settings, hourly details, or the add-location page is open. It does nothing when only one location is configured. No service restart is needed.

Hourly details for Today begin at the current local hour and hide earlier hours. If six or fewer hours remain, the view also includes up to four early hours from tomorrow. Details for another forecast day initially center the scroll position on 8 AM; the full day remains available from midnight to 11 PM. Each day starts at its own position when opened.

`startup.autoStart` enables the desktop login launcher. `startup.kiosk` selects full-screen kiosk mode (`true`) or a maximized browser window (`false`). On a local Linux or Raspberry Pi session, enabling auto-start in Settings installs the desktop login hook automatically and writes per-device overrides to `device-settings.json`; those overrides take precedence over the JSON defaults. On Raspberry Pi OS with labwc, Dayglance adds a marked entry to `~/.config/labwc/autostart`; on other Linux desktops it creates `~/.config/autostart/dayglance.desktop`. Changes apply at the next desktop login or next launcher run. `install-autostart.sh` remains available for manual or keyboard-free setup.

Browser preferences changed in the Settings menu are stored in that browser and take precedence over `config.json`. On a fresh browser profile, the JSON preferences are used directly. To switch an existing browser back to copied JSON defaults, clear Dayglance's saved site data for that browser. Keep this file free of API keys, passwords, and other secrets; the browser downloads it as a public static file.

## Local weather-station integration

Each saved city may be associated with zero or one station observation source. **Settings → Local Weather Stations** lets you manage reusable cloud API key profiles, add/edit/remove cloud station entries, assign stations to cities, and see reading status. Ambient Weather profiles contain the user API key and application key; Weather Underground profiles contain the Weather Company API key. Save or replace keys using masked fields; Dayglance never returns key values to the browser. Keys are written to the private `device-station-credentials.json` file, and cloud station definitions to `device-station-settings.json`. Both files are ignored by Git and written with owner-only permissions on Linux. You can reuse one profile for multiple devices, and you may define multiple profiles for each provider. This supports ten or more cities without duplicating keys: for example, five stations can use one Ambient profile and five can use one Weather Underground profile. Cloud changes made in Settings take effect immediately; the poller checks for data on its next one-minute cycle. `config.json` remains the supported way to provision cloud sources and local uploads. Config-defined sources are read-only in Settings except for their city association. Changes to `stationReceiver` or a local-upload source in `config.json` require a service restart. There is no three-city cap: add a source per city/station pair, with unique IDs; provider quotas and the one-source-per-city rule still apply. A station does not become an extra carousel location: its live measurements appear on the selected city's dashboard, while the forecast and hourly view continue to use Open-Meteo. Station values are labeled as observations and automatically stop being used when their observation timestamp is older than `staleAfterSeconds`.

For manual device provisioning, copy [`device-station-settings.example.json`](../../device-station-settings.example.json) to the ignored `device-station-settings.json` file beside `server.py`, then adjust station IDs, profiles, and city IDs. Keep provider keys in `device-station-credentials.json` or enter them in Settings. Do not commit the private runtime files.

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
  "stationId": "KEXAMPLE123",
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

