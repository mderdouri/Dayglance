# Dayglance rain radar

Dayglance combines **RainViewer for recent observed radar** with **Rainbow Weather for forecast precipitation tiles**. Open Rain radar from the dashboard's umbrella button. Choose **Past 2 hours** or **Next 4 hours**; choosing the active option again clears the selection. The selected frames play automatically after their map tiles finish loading. There is no timeline slider or separate play control. The map centers on the currently selected saved location. Pan and zoom are available, up to zoom level 7 in Dayglance.

**Next 4 hours** requires a Rainbow Weather API key. Without one, the button is highlighted and reads **Set up**; tapping it briefly explains where to add the key. Past radar remains available without an account. Manage the key in **Settings → Radar & Provider Account**.

The radar page closes after its configurable idle timeout. The default is one minute; choose 15 seconds, 30 seconds, 1 minute, or 5 minutes in **Settings → Radar & Provider Account**, or set `preferences.radarIdleTimeoutSeconds` in `config.json`. Touch, pointer, keyboard, wheel, and map interaction reset the timer; automatic frame changes do not. This limits accidental long sessions, but it is not an account-wide spending limit.

The map uses OpenStreetMap for its background. It needs internet access to load the map, radar metadata, and tiles. If a provider is unavailable, Dayglance reports that and keeps the rest of the forecast app usable. When the display wakes from a screensaver, the app refreshes the radar frames while keeping the radar view open.

The [screenshot gallery](../screenshots/README.md) includes a sample radar settings view.

![Settings showing the Rainbow account setup and device usage estimate](../screenshots/dayglance-radar-settings-2026-10-15.png)

The local 800×480 settings preview below shows the configurable idle timeout. It defaults to one minute.

![Local 800×480 settings preview with the precipitation map idle timeout](../screenshots/dayglance-radar-timeout-settings-20261016.png)

## Set up Rainbow Weather on a device

Rainbow accounts and billing belong to each Dayglance user. Dayglance does not create accounts, enroll a payment method, or sign up on the user's behalf.

1. On the Pi's local Dayglance screen, open **Settings → Radar & Provider Account**.
2. Select **Create account / get API key**. Create a Rainbow developer account and generate an API key in its developer portal.
3. Return to Dayglance on the Pi, paste the key into **Rainbow Weather API key**, and select **Save key**. Dayglance validates the key with Rainbow before saving it.
4. Check the usage estimate shown in Settings and use **Pricing and usage dashboard** for Rainbow's actual account-wide usage and billing. Account usage may include other devices or applications using the same key/account.

The key is stored on this device in the ignored, device-local `device-radar-key.json`, with owner-only file permissions on POSIX systems. The server does not return the key to the browser or put it in `config.json`, screenshots, source control, or browser storage. The Rainbow and RainViewer proxy endpoints and credential management accept requests only from the local browser on the Pi, to keep quota and account access tied to that device. A browser connected from another LAN device will not get radar frames. Remove the saved key with **Remove** in Settings. Back up or restore this secret only through a separately protected device configuration process; do not publish it.

To provision without a keyboard on the Pi, temporarily open the local dashboard from a keyboard-enabled browser session only if that browser is running on the Pi itself. The credential API intentionally rejects a remote LAN browser. A future documented device provisioning command could be added if keyboard-free first-time key setup is needed.

## Allowances and cost visibility

Rainbow's currently published developer pricing provides a free monthly allowance, then pay-as-you-go billing:

| Rainbow API | Monthly free allowance | Published price after allowance | Used by Dayglance radar? |
|---|---:|---:|---|
| Precipitation map tiles | 30,000 tiles | $0.20 per 1,000 tiles | Yes. The device counter estimates successful forecast-tile requests. |
| Point precipitation nowcast | 5,000 requests | $0.10 per 1,000 requests | No. Dayglance displays forecast map tiles instead of calling this JSON endpoint. |

The free allowance resets each calendar month according to Rainbow's published terms. Dayglance tracks successful Rainbow tile responses made through **this Dayglance server**. Settings shows this device's count and the remaining amount estimated against the 30,000-tile allowance. It is a local estimate, not an account balance: it cannot see usage from another Dayglance device, another app, or other API keys in the Rainbow account. The Rainbow dashboard is authoritative. Local usage is checkpointed at most hourly to reduce SD-card writes and flushed on a normal server shutdown; after an abrupt power loss or forced termination, the estimate can be short by up to about one hour of requests.

**Paid usage is disabled by default.** When it is disabled, this server stops requesting Rainbow tiles once its local counter reaches 30,000 for the month. A local Settings action with a cost warning explicitly enables pay-as-you-go for this device; the choice is stored with local usage state and turns off when the Rainbow key is removed. This guard is device-local only. If another app or device has already used some or all of the same account allowance, the local counter can overstate what remains and cannot guarantee that requests will stay within the account's free quota. For the strongest protection, use a dedicated Rainbow key/account for Dayglance, keep paid usage disabled until needed, and check Rainbow's dashboard before opting in. Rainbow account billing controls still determine whether overage requests are charged.

As a rough estimate, if the monthly successful tile count passes 30,000, the published usage rate is $0.20 per 1,000 additional tile calls. Actual totals and any rounding, taxes, plan settings, billing threshold, and account-wide usage must be confirmed in Rainbow's dashboard and current terms before enabling pay-as-you-go. Dayglance never sets up a payment method or changes Rainbow account billing.

Rainbow updates its radar snapshot about every 10 minutes and exposes precipitation frames up to four hours ahead at ten-minute forecast offsets. A map view loads multiple tiles; zooming, panning, selecting forecast mode, animation, and reopening the radar view all consume tile calls. Automatic playback waits for visible map tiles to load and then advances no faster than every seven seconds. Dayglance's tracker counts successful Rainbow image-tile responses, not RainViewer requests or OpenStreetMap base-map tiles.

## RainViewer recent radar limits

RainViewer's public Weather Maps API currently offers approximately two hours of past frames at ten-minute intervals. Its free API requires no account or API key, is intended for personal and educational use, and has no service-level availability guarantee. Current published constraints include maximum zoom 7, the Universal Blue color palette, and a 100-request-per-IP-per-minute limit. Future/nowcast frames were discontinued on January 1, 2026, which is why Dayglance uses Rainbow for the forecast side. Dayglance displays the required RainViewer credit on the map.

## Data sources and current terms

- [RainViewer Weather Maps API](https://www.rainviewer.com/api/weather-maps-api.html) and [API transition summary](https://www.rainviewer.com/api/transition-faq.html)
- [Rainbow Weather API reference](https://doc.rainbow.ai/api-ref/scalar?spec=tiles), [developer pricing](https://developer.rainbow.ai/), and [terms of service](https://developer.rainbow.ai/terms-of-service)
- [OpenStreetMap tile usage policy](https://operations.osmfoundation.org/policies/tiles/) and [copyright/attribution](https://www.openstreetmap.org/copyright)

These limits and prices are provider-controlled and can change. Recheck the linked official documentation before a public release or paid-tier onboarding. RainViewer's free API terms are not a commercial-use license; anyone distributing or operating Dayglance commercially must confirm both providers' applicable terms independently.

