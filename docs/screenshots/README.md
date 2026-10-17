# Dayglance screenshots

All project screenshots are kept in this folder so they are easy to find and do not clutter the repository root. The README embeds only the live dashboard and hourly detail views; this gallery keeps the rest of the product and device captures available.

## Live dashboard

![Live DevPi dashboard with the modeled air-quality estimate](devpi-air-quality-2026-10-15.png)

![Dashboard preview with current observations from an associated local weather station](dayglance-local-station-dashboard-20261016.png)

This 800×480 browser capture uses synthetic test forecast and station readings to verify the local-station UI; it is not a measurement from the physical station.

![Earlier DevPi dashboard capture](dayglance-devpi-20261015.png)

![Dashboard with an active severe weather alert banner](dayglance-severe-alert-dashboard-20261016.png)

This isolated 800×480 preview uses a synthetic National Weather Service alert payload to demonstrate the banner and layout. The forecast values were fetched during preview and change over time; this is not a physical touchscreen capture or a live warning.

![Severe weather alert detail view](dayglance-severe-alert-details-20261016.png)

This isolated 800×480 preview uses synthetic alert details. The detail card is vertically swipeable when alert text extends beyond the screen.

![Dayglance dashboard preview with a prominent city name, smaller region and country, and the edit button](dayglance-city-header-20261016.png)

This interface preview uses simulated forecast values; it demonstrates the location heading layout, not live conditions.

## Forecast details

![Hourly detail cards with touch-friendly navigation](hourly-details.png)

![Clock cues beside time labels on the main temperature graph and hourly forecast cards](dayglance-hour-context-cues-20261016.png)

![Clock cues beside time labels in the hourly detail strip](dayglance-hourly-time-context-20261016.png)

This 800×480 preview uses synthetic forecast data and an example location.

![Hourly detail view showing the 24-hour strip](hourly-view.jpg)

![Hourly detail view with touch scrolling and the optional arrow bumpers hidden by default](hourly-view-bumpers-off-20261016.png)

This 800×480 browser preview uses synthetic hourly data; it shows the default view without arrow bumpers. Swipe, drag, and scrolling remain available.

![Today's hourly detail starting at the current hour](dayglance-hourly-today-20261015.png)

## Setup and settings

![First-launch location setup](first-launch.png)

![Settings with location and startup controls](dayglance-settings-location-first-20261015.png)

![Settings showing the hourly view return timer and one-minute default](dayglance-hourly-timeout-settings-20261016.png)

![Settings showing the city assignment for a local weather station](dayglance-local-station-settings-20261016.png)

![Settings showing available Ambient Weather and Weather Underground connections](dayglance-station-connections-settings-20261016.png)

![Settings home with a full-width Connections & Alerts shortcut at the top and balanced settings groups below](dayglance-settings-home-connections-first-20261017.png)

This isolated 800×480 browser capture uses a sample Washington, D.C. location. Connections & Alerts spans the first row, Locations remains full width beneath it, and the remaining settings are paired by category. At narrower widths, the same order stacks into one column. This is not a physical touchscreen capture.

![Connections & Alerts settings showing severity controls and current feed status](dayglance-connections-alerts-20261016.png)

These isolated 800×480 captures use the current Settings structure. The status dot reflects the feed state during preview; synthetic alert data is used only to make the active-alert state visible.

This isolated 800×480 Chrome preview uses the current Settings markup and styles; it verifies that cloud/local connection options are discoverable, but is not a physical DevPi touchscreen capture.

![Cloud station manager showing reusable Ambient Weather and Weather Underground key profiles](dayglance-station-manager-profiles-20261016.png)

![Cloud station form showing a reusable profile and city association](dayglance-station-manager-sources-20261016.png)

These isolated 800×480 Chrome previews use synthetic profile labels, station IDs, locations, and keys. They demonstrate the cloud-station manager; no real credentials or physical touchscreen are shown.

![Vertically swipeable settings with a pinned close control](settings-touch-scroll.jpg)

## Air-quality preview


![Air-quality tile preview at 800 by 480](dayglance-air-quality-2026-10-15.png)

## Rain radar

![Rain radar settings with the one-minute idle timeout](dayglance-radar-timeout-settings-20261016.png)

![Dayglance dashboard after deploying radar controls to DevPi](dayglance-radar-ux-devpi-20261015.png)
