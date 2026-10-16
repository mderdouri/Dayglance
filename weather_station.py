"""Helpers for validating and normalizing local personal-weather-station uploads."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import time
from typing import Mapping


_FIELDS = {
    "tempf": (-150.0, 150.0),
    "humidity": (0.0, 100.0),
    "winddir": (0.0, 360.0),
    "windspeedmph": (0.0, 300.0),
    "windgustmph": (0.0, 350.0),
    "rainin": (0.0, 100.0),
    "dailyrainin": (0.0, 1000.0),
    "baromin": (10.0, 40.0),
    "uv": (0.0, 30.0),
    "solarradiation": (0.0, 2500.0),
    "dewptf": (-150.0, 150.0),
    "indoortempf": (-150.0, 150.0),
    "indoorhumidity": (0.0, 100.0),
}
_FIELD_ALIASES = {
    "rainin": ("hourlyrainin",),
    "baromin": ("baromrelin",),
    "indoortempf": ("tempinf",),
    "indoorhumidity": ("humidityin",),
}


def normalize_upload(values: Mapping[str, object], received_at: float | None = None) -> dict[str, object]:
    """Return a bounded observation containing only known, plausible weather fields."""
    received = time.time() if received_at is None else float(received_at)
    lower = {str(key).lower(): value for key, value in values.items()}
    observation: dict[str, object] = {}

    for field, (minimum, maximum) in _FIELDS.items():
        raw = lower.get(field)
        if raw is None:
            raw = next((lower[name] for name in _FIELD_ALIASES.get(field, ()) if name in lower), None)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and minimum <= value <= maximum:
            observation[field] = value

    if not any(field in observation for field in ("tempf", "humidity", "windspeedmph", "baromin")):
        raise ValueError("Upload contains no usable outdoor weather readings")

    dateutc = str(lower.get("dateutc", "now")).strip()
    if not dateutc or dateutc.lower() == "now":
        observed_at = received
    else:
        try:
            observed_at = datetime.strptime(dateutc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
        except ValueError as error:
            raise ValueError("dateutc must be 'now' or a UTC timestamp in YYYY-MM-DD HH:MM:SS format") from error
        if observed_at > received + 300 or observed_at < received - 7 * 24 * 60 * 60:
            raise ValueError("dateutc is outside the accepted seven-day observation window")

    observation["observedAt"] = observed_at
    observation["receivedAt"] = received
    return observation


def normalize_weather_company_pws(record: Mapping[str, object], received_at: float | None = None) -> dict[str, object]:
    """Convert The Weather Company's current PWS record into Dayglance units."""
    imperial = record.get("imperial", {})
    if not isinstance(imperial, Mapping):
        imperial = {}
    values: dict[str, object] = {
        "tempf": imperial.get("temp"),
        "humidity": record.get("humidity"),
        "winddir": record.get("winddir"),
        "windspeedmph": imperial.get("windSpeed"),
        "windgustmph": imperial.get("windGust"),
        "rainin": imperial.get("precipRate"),
        "dailyrainin": imperial.get("precipTotal"),
        "baromin": imperial.get("pressure"),
        "uv": record.get("uv"),
        "solarradiation": record.get("solarRadiation"),
        "dewptf": imperial.get("dewpt"),
    }
    epoch = record.get("epoch")
    try:
        if epoch is not None:
            values["dateutc"] = datetime.fromtimestamp(float(epoch), timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        else:
            timestamp = str(record.get("obsTimeUtc", "")).strip().replace("Z", "+00:00")
            values["dateutc"] = datetime.fromisoformat(timestamp).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OverflowError, OSError) as error:
        raise ValueError("Weather Company observation has an invalid UTC timestamp") from error
    return normalize_upload(values, received_at=received_at)


def freshness(observation: Mapping[str, object] | None, stale_after_seconds: int, now: float | None = None) -> dict[str, object]:
    """Add age and freshness metadata without mutating the in-memory sample."""
    if not observation:
        return {"available": False, "fresh": False, "ageSeconds": None, "observation": None}
    current = time.time() if now is None else float(now)
    observed = float(observation.get("observedAt", observation.get("receivedAt", 0)))
    age = max(0, int(current - observed))
    return {
        "available": True,
        "fresh": age <= stale_after_seconds,
        "ageSeconds": age,
        "observation": dict(observation),
    }
