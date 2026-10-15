# Third-party notices

## Open-Meteo weather and geocoding APIs

Dayglance requests forecast data from the [Open-Meteo Forecast API](https://open-meteo.com/en/docs) and location suggestions from the [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api). These services are hosted by Open-Meteo and are not included in this repository. Dayglance displays Open-Meteo attribution in the app.

Dayglance also requests current U.S. AQI and PM2.5 estimates from the [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api). Its CAMS-based results are modeled grid estimates, not readings from a local air-quality sensor. Open-Meteo requires clear attribution to both Open-Meteo and the [Copernicus Atmosphere Monitoring Service (CAMS)](https://atmosphere.copernicus.eu/); the app displays both credits. Displayed U.S. AQI category labels follow the [U.S. EPA Air Quality Index scale](https://www.airnow.gov/aqi/aqi-basics/).

Open-Meteo states that data served by its APIs is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/), which requires appropriate credit. Its free hosted API is for non-commercial use and has request limits and no uptime guarantee. Commercial use requires the applicable Open-Meteo commercial plan/license. Terms and limits can change; check the current [Open-Meteo pricing page](https://open-meteo.com/en/pricing) before deployment.

## GeoNames location data

The Open-Meteo Geocoding API documents its location data as based on [GeoNames](https://www.geonames.org/). Refer to the [Geocoding API documentation](https://open-meteo.com/en/docs/geocoding-api) for attribution and service details.

## Scope of the MIT license

The [MIT License](../../LICENSE) applies to the original software files in this repository. It does not grant rights to external APIs, their service infrastructure, or third-party datasets beyond the terms granted by their respective providers.
