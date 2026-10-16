# Local weather stations

Dayglance can display live observations from one local weather station on a saved city. The station is linked to a city rather than shown as another location. Dayglance keeps the selected forecast provider for sunrise, hourly forecasts, daily outlooks, and the temperature graph. Station-backed current measurements are identified as observations and replace forecast values only while the station sample is fresh.

## Supported connection

The first supported integration is Ambient Weather local upload. Dayglance accepts both the station's native Ambient Weather fields and Weather Underground-compatible upload fields. The station initiates an upload to Dayglance on the local network. Dayglance does not poll the station, access its cloud account, or require an internet-accessible listener. Cloud station integrations are not implemented yet.

## Before setup

1. Give the Pi and station stable private LAN addresses, preferably DHCP reservations. Use the station's observed IP as `sourceIp`.
2. Check that the station console and its firmware expose a custom server/custom upload setting in the companion app or console menu. Ambient Weather's [WS-2902 FAQ](https://ambientweather.com/faqs/question/tags/tag/WS-2902A/) documents the AWNET custom-server fields and both supported formats; the [WS-2902C manual](https://ambientweather.com/mwdownloads/download/link/id/1174) is a model-specific reference. Model revisions and firmware differ. The Amazon listing for the station used during Dayglance development appears to be in the WS-2902 family, but the exact console revision and installed firmware have not yet been confirmed.
3. Choose an unused port from 1024 through 65535 (the example uses 8082). Do not set up a router port-forward.

## Configure Dayglance

Edit the project-root `config.json`. Set `bindAddress` to the Pi's private LAN interface address, then add a source entry with the station's private IP. For example:

```json
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
```

The addresses are examples, not a recommended range. The Pi address must be assigned to its network interface; the station source address must match the sender address seen by the Pi. `id` is unique and stable. `name` is the label shown in Settings. `locationId` can be null and is normally selected in Settings. A city can have at most one station. `staleAfterSeconds` accepts 30–3600 and controls how long a reading can be used after its observation timestamp.

The listener refuses `0.0.0.0`, loopback, and public bind addresses. It accepts requests only on the configured path from configured station IPs. Keep the port limited to your trusted LAN with your router/firewall. Do not place station passwords, API keys, or other credentials in `config.json`; this config is served to the browser. The upload protocol may include an ID and password field; Dayglance ignores these values and never logs upload query strings.

Restart the Dayglance service after changing `stationReceiver` or adding/enabling a station. It starts no listener when `stationIntegrations` is empty or all sources are disabled. A bad station config is logged while the weather dashboard continues to start without the receiver.

## Configure the station upload

In the station's app, open its custom server/custom upload configuration. Field names differ, but enter the values matching your Dayglance config:

- Server: the Pi's private LAN address, such as `192.168.1.50`.
- Protocol: HTTP on the local network.
- Port: `8082` (or the port selected in `config.json`).
- Path: `/weatherstation/updateweatherstation.php` (or the configured path).
- Upload protocol/format: Ambient Weather native format or Weather Underground-compatible format. Dayglance supports both; use the one offered and documented for the exact console/firmware.
- Upload interval: use the shortest reasonable interval offered by the station, ideally around 1–5 minutes.

Save the station settings, then allow an upload interval to pass. In Dayglance, open **Settings → Local Weather Stations** and associate the station with the matching saved city. It may display “Waiting for first reading” until an upload arrives. If the custom upload option does not exist in the station's app/firmware, this adapter cannot receive data from that unit without a supported intermediary.

## Data and storage behavior

Dayglance accepts supported numeric outdoor observations: temperature, humidity, wind direction/speed/gust, rain rate and daily rain, pressure, UV, solar radiation, and dew point. Values outside plausible limits are ignored. At least one usable outdoor reading is required. Units are normalized for display. Not every station submits every field.

Only the latest sample for each station is kept in server memory. It is cleared on service restart and no history is stored. The browser refreshes receiver status every 30 seconds but does not persist samples to browser storage. The dashboard falls back to Open-Meteo current conditions when the sample becomes stale or the listener is unavailable. Forecasts remain clearly separated from the station's current observations; the local reading does not rewrite hourly or daily forecasts.

## Troubleshooting

- **Waiting for first reading:** confirm that Dayglance service restarted with a valid enabled source, that the station's sender IP matches `sourceIp`, and that the station's target address, port, path, and protocol exactly match `stationReceiver`.
- **Receiver configuration error:** check the service log. Confirm `bindAddress` is the Pi's actual private address, the port is available, each station has a unique `id` and `sourceIp`, and no two sources have the same `locationId` in the JSON file.
- **Stale reading:** verify that uploads continue and that the station's UTC `dateutc` is current. Increase `staleAfterSeconds` only if the station uploads at a longer interval.
- **Wrong city:** change the source's city assignment in Settings. Each city accepts only one source; another source already assigned to that city must be moved first.
- **Station has no custom upload:** check its exact model and firmware documentation. Ambient Weather model variants differ; do not assume that a similar model's custom-server feature is available.

See [Configuration](CONFIGURATION.md) for the supported JSON configuration path and its precedence rules.
