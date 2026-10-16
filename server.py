#!/usr/bin/env python3
"""Small standard-library server for the Dayglance static app."""

from __future__ import annotations

import argparse
import ipaddress
import json
import math
import os
import shlex
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, unquote, urlsplit
from urllib.request import Request, urlopen

from weather_station import (
    freshness as station_freshness,
    normalize_upload,
    normalize_weather_company_pws,
)


ROOT = Path(__file__).resolve().parent
DEVICE_SETTINGS_PATH = ROOT / "device-settings.json"
RADAR_CREDENTIALS_PATH = ROOT / "device-radar-key.json"
RADAR_USAGE_PATH = ROOT / "device-radar-usage.json"
STATION_CREDENTIALS_PATH = ROOT / "device-station-credentials.json"
STATION_SETTINGS_PATH = ROOT / "device-station-settings.json"
CONFIG_PATH = ROOT / "config.json"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "dayglance.desktop"
STARTUP_SUPPORTED = sys.platform.startswith("linux")
FILES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "air-quality.js": "text/javascript; charset=utf-8",
    "detail-hours.js": "text/javascript; charset=utf-8",
    "radar.js": "text/javascript; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "manifest.webmanifest": "application/manifest+json; charset=utf-8",
    "config.json": "application/json; charset=utf-8",
    "sw.js": "text/javascript; charset=utf-8",
}
RAINBOW_BASE = "https://api.rainbow.ai"
RAINVIEWER_METADATA = "https://api.rainviewer.com/public/weather-maps.json"
RAINBOW_MONTHLY_ALLOWANCES = {"tiles": 30000, "nowcast": 5000}
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"
NWS_ALERTS_CACHE_SECONDS = 300
USAGE_FLUSH_SECONDS = 3600
_usage_lock = threading.Lock()
_usage_state: dict[str, object] = {"month": "", "tiles": 0, "nowcast": 0, "allowPaidUsage": False}
_usage_last_write = 0.0
_station_lock = threading.Lock()
_station_observations: dict[str, dict[str, object]] = {}
_station_config: dict[str, object] = {"receiver": {}, "integrations": []}
_station_receiver_status = "disabled"
_station_source_status: dict[str, str] = {}
_station_cloud_stop = threading.Event()
_alerts_lock = threading.Lock()
_alerts_cache: dict[str, dict[str, object]] = {}
_provider_health_lock = threading.Lock()
_provider_health: dict[str, dict[str, object]] = {
    "rainviewer": {"healthy": None, "checkedAt": None, "message": "Not checked yet"},
    "rainbow": {"healthy": None, "checkedAt": None, "message": "Not checked yet"},
}


def record_provider_health(provider: str, status: int, message: str = "") -> None:
    if provider not in _provider_health:
        return
    healthy = 200 <= status < 300
    safe_message = "Connected" if healthy else f"Request failed (HTTP {status})"
    if message and status >= 400:
        safe_message = message[:120]
    with _provider_health_lock:
        _provider_health[provider] = {
            "healthy": healthy,
            "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": safe_message,
        }


def provider_health_snapshot() -> dict[str, dict[str, object]]:
    with _provider_health_lock:
        return {name: dict(status) for name, status in _provider_health.items()}


def active_alerts_for_point(latitude: float, longitude: float) -> dict[str, object]:
    """Return cached NWS active alerts for a point; upstream failures may use stale data."""
    cache_key = f"{latitude:.3f},{longitude:.3f}"
    now = time.time()
    with _alerts_lock:
        cached = _alerts_cache.get(cache_key)
        if cached and now - float(cached["cachedAt"]) < NWS_ALERTS_CACHE_SECONDS:
            return {key: value for key, value in cached.items() if key != "cachedAt"}
        if cached and now < float(cached.get("retryAt", 0)):
            return {key: value for key, value in cached.items() if key not in ("cachedAt", "retryAt")}

    url = f"{NWS_ALERTS_URL}?{urlencode({'point': cache_key})}"
    request = Request(url, headers={
        "Accept": "application/geo+json",
        "User-Agent": "Dayglance/1.0 (https://github.com/mderdouri/Dayglance)",
    })
    try:
        with urlopen(request, timeout=10) as response:
            if response.status != 200:
                raise OSError(f"National Weather Service returned HTTP {response.status}")
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
            raise ValueError("Unexpected National Weather Service alert response")
        features = []
        for feature in payload["features"]:
            if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
                continue
            properties = feature["properties"]
            fields = (
                "id", "areaDesc", "sent", "effective", "onset", "expires", "ends",
                "status", "messageType", "category", "severity", "certainty", "urgency",
                "event", "headline", "description", "instruction", "response", "web",
            )
            features.append({
                "id": feature.get("id") or properties.get("id"),
                "properties": {key: properties.get(key) for key in fields if key in properties},
            })
        result = {"features": features, "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "stale": False}
        with _alerts_lock:
            _alerts_cache[cache_key] = {**result, "cachedAt": now}
            if len(_alerts_cache) > 64:
                oldest_key = min(_alerts_cache, key=lambda key: float(_alerts_cache[key]["cachedAt"]))
                _alerts_cache.pop(oldest_key, None)
        return result
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        with _alerts_lock:
            cached = _alerts_cache.get(cache_key)
            if cached:
                cached["stale"] = True
                cached["retryAt"] = now + NWS_ALERTS_CACHE_SECONDS
                cached["error"] = "National Weather Service alert data could not be refreshed"
                return {key: value for key, value in cached.items() if key not in ("cachedAt", "retryAt")}
            _alerts_cache[cache_key] = {"features": [], "checkedAt": None, "stale": True, "error": "National Weather Service alert data is temporarily unavailable", "cachedAt": now, "retryAt": now + NWS_ALERTS_CACHE_SECONDS}
        return {"features": [], "checkedAt": None, "stale": True, "error": "National Weather Service alert data is temporarily unavailable"}


def read_radar_key() -> str:
    try:
        data = json.loads(RADAR_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return data.get("rainbowApiKey", "") if isinstance(data, dict) else ""
    except (OSError, ValueError, json.JSONDecodeError):
        return ""


def write_private_json(path: Path, data: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        if os.name == "posix":
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(temporary, flags, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    descriptor = -1
                    stream.write(json.dumps(data, indent=2) + "\n")
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        else:
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def current_usage() -> dict[str, object]:
    global _usage_last_write
    month = time.strftime("%Y-%m", time.gmtime())
    with _usage_lock:
        if _usage_state.get("month") != month:
            _usage_state.update({"month": month, "tiles": 0, "nowcast": 0})
            _usage_last_write = 0.0
        return {
            "month": month,
            "tiles": int(_usage_state.get("tiles", 0)),
            "nowcast": int(_usage_state.get("nowcast", 0)),
            "allowPaidUsage": _usage_state.get("allowPaidUsage") is True,
            "tileAllowance": RAINBOW_MONTHLY_ALLOWANCES["tiles"],
            "nowcastAllowance": RAINBOW_MONTHLY_ALLOWANCES["nowcast"],
        }


def record_rainbow_usage(kind: str) -> None:
    global _usage_last_write
    if kind not in ("tiles", "nowcast"):
        return
    current_usage()
    with _usage_lock:
        _usage_state[kind] = int(_usage_state.get(kind, 0)) + 1
        now = time.monotonic()
        if now - _usage_last_write >= USAGE_FLUSH_SECONDS:
            write_private_json(RADAR_USAGE_PATH, {
                "month": _usage_state["month"],
                "tiles": _usage_state["tiles"],
                "nowcast": _usage_state["nowcast"],
                "allowPaidUsage": _usage_state.get("allowPaidUsage") is True,
            })
            _usage_last_write = now


def load_radar_usage() -> None:
    global _usage_last_write
    try:
        data = json.loads(RADAR_USAGE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("month") == time.strftime("%Y-%m", time.gmtime()):
            _usage_state.update({
                "month": data["month"],
                "tiles": max(0, int(data.get("tiles", 0))),
                "nowcast": max(0, int(data.get("nowcast", 0))),
                "allowPaidUsage": data.get("allowPaidUsage") is True,
            })
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass


def flush_radar_usage() -> None:
    with _usage_lock:
        if _usage_state.get("month"):
            write_private_json(RADAR_USAGE_PATH, {
                "month": _usage_state["month"],
                "tiles": _usage_state["tiles"],
                "nowcast": _usage_state["nowcast"],
                "allowPaidUsage": _usage_state.get("allowPaidUsage") is True,
            })


def save_paid_usage_setting(enabled: bool) -> None:
    global _usage_last_write
    current_usage()
    with _usage_lock:
        _usage_state["allowPaidUsage"] = enabled
        write_private_json(RADAR_USAGE_PATH, {
            "month": _usage_state["month"],
            "tiles": _usage_state["tiles"],
            "nowcast": _usage_state["nowcast"],
            "allowPaidUsage": enabled,
        })
        _usage_last_write = time.monotonic()


def load_station_configuration(*, managed_override: list[dict[str, object]] | None = None) -> dict[str, object]:
    """Read and validate city-scoped local and cloud station definitions."""
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        config = {}
    raw_receiver = config.get("stationReceiver", {}) if isinstance(config, dict) else {}
    raw_sources = config.get("stationIntegrations", []) if isinstance(config, dict) else []
    if not isinstance(raw_receiver, dict) or not isinstance(raw_sources, list):
        raise ValueError("stationReceiver must be an object and stationIntegrations must be an array")
    config_source_ids = {source["id"] for source in raw_sources if isinstance(source, dict) and isinstance(source.get("id"), str)}

    if managed_override is None:
        try:
            station_settings = json.loads(STATION_SETTINGS_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            station_settings = {}
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("Device station settings are unreadable; fix device-station-settings.json") from error
        managed_override = station_settings.get("integrations", []) if isinstance(station_settings, dict) else None
    if not isinstance(managed_override, list):
        raise ValueError("Device station settings integrations must be an array")
    for managed_source in managed_override:
        if not isinstance(managed_source, dict) or managed_source.get("connection") != "cloud-api":
            raise ValueError("Settings can manage cloud API stations only; local upload stays in config.json")
        raw_sources.append({**managed_source, "managed": True, "enabled": True})

    receiver = {
        "bindAddress": raw_receiver.get("bindAddress", "127.0.0.1"),
        "port": raw_receiver.get("port", 8082),
        "path": raw_receiver.get("path", "/weatherstation/updateweatherstation.php"),
    }
    integrations: list[dict[str, object]] = []
    ids: set[str] = set()
    source_ips: set[str] = set()
    linked_locations: set[str] = set()
    for source in raw_sources:
        if not isinstance(source, dict):
            raise ValueError("Each station integration must be an object")
        if source.get("enabled") is not True:
            continue
        source_id = source.get("id")
        location_id = source.get("locationId")
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 80:
            raise ValueError("Enabled station integrations need a short, non-empty id")
        if location_id is not None and (not isinstance(location_id, str) or not location_id.strip() or len(location_id) > 120):
            raise ValueError(f"Station integration {source_id!r} locationId must be a non-empty string or null")
        if source_id in ids:
            raise ValueError(f"Duplicate station integration id: {source_id}")
        if location_id and location_id in linked_locations:
            raise ValueError(f"Only one enabled station integration can be assigned to {location_id}")
        ids.add(source_id)
        if location_id:
            linked_locations.add(location_id)
        provider, connection = source.get("provider"), source.get("connection")
        supported = provider == "ambient-weather" and connection in ("local-upload", "cloud-api")
        supported = supported or (provider == "weather-underground" and connection == "cloud-api")
        if not supported:
            raise ValueError(f"Unsupported station adapter for {source_id!r}; use ambient-weather local-upload/cloud-api or weather-underground cloud-api")
        try:
            stale_after = int(source.get("staleAfterSeconds", 600))
        except (ValueError, TypeError) as error:
            raise ValueError(f"Station {source_id!r} staleAfterSeconds must be an integer") from error
        local_source_ip = None
        if connection == "local-upload":
            try:
                source_ip = ipaddress.ip_address(str(source.get("sourceIp", "")))
                bind_ip = ipaddress.ip_address(str(receiver["bindAddress"]))
                port = int(receiver["port"])
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid network setting for station {source_id!r}") from error
            if source_ip.version != 4 or not source_ip.is_private or source_ip.is_loopback:
                raise ValueError(f"Station {source_id!r} sourceIp must be a private IPv4 address")
            if str(source_ip) in source_ips:
                raise ValueError("Each enabled local station must have a unique sourceIp")
            source_ips.add(str(source_ip))
            if bind_ip.version != 4 or not bind_ip.is_private or bind_ip.is_loopback or bind_ip.is_unspecified:
                raise ValueError("Enabled stationReceiver.bindAddress must be the Pi's specific private IPv4 address")
            if not 1024 <= port <= 65535:
                raise ValueError("stationReceiver.port must be between 1024 and 65535")
            path = receiver["path"]
            if not isinstance(path, str) or not path.startswith("/") or "?" in path or ".." in path or len(path) > 160:
                raise ValueError("stationReceiver.path must be a short absolute URL path without query or traversal")
            local_source_ip = str(source_ip)
        elif provider == "ambient-weather":
            device_id = source.get("deviceId")
            credentials_id = source.get("credentialsId", source_id)
            normalized_device_id = str(device_id or "").replace(":", "").replace("-", "")
            if len(normalized_device_id) != 12 or any(char not in "0123456789abcdefABCDEF" for char in normalized_device_id):
                raise ValueError(f"Cloud station {source_id!r} needs deviceId as a 12-digit hexadecimal Ambient MAC address")
            if not isinstance(credentials_id, str) or not credentials_id.strip() or len(credentials_id) > 80:
                raise ValueError(f"Cloud station {source_id!r} needs a short credentialsId")
            device_id = str(device_id).strip()
        else:
            station_id = source.get("stationId")
            credentials_id = source.get("credentialsId", source_id)
            if not isinstance(station_id, str) or not 3 <= len(station_id.strip()) <= 32 or not station_id.replace("-", "").isalnum():
                raise ValueError(f"Weather Underground station {source_id!r} needs a valid stationId")
            if not isinstance(credentials_id, str) or not credentials_id.strip() or len(credentials_id) > 80:
                raise ValueError(f"Cloud station {source_id!r} needs a short credentialsId")
            station_id = station_id.strip()
        if not 30 <= stale_after <= 3600:
            raise ValueError(f"Station {source_id!r} staleAfterSeconds must be between 30 and 3600")
        integration = {
            "id": source_id,
            "name": str(source.get("name") or "Local weather station")[:80],
            "locationId": location_id,
            "provider": provider,
            "connection": connection,
            "staleAfterSeconds": stale_after,
            "managed": source.get("managed") is True and source_id not in config_source_ids,
        }
        if local_source_ip:
            integration["sourceIp"] = local_source_ip
        elif provider == "ambient-weather":
            integration["deviceId"] = device_id
            integration["credentialsId"] = credentials_id.strip()
        else:
            integration["stationId"] = station_id
            integration["credentialsId"] = credentials_id.strip()
        integrations.append(integration)

    return {"receiver": receiver, "integrations": integrations}


def read_station_credentials() -> dict[str, object]:
    """Read secrets for cloud adapters from the private, device-local file."""
    try:
        data = json.loads(STATION_CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def station_credentials_for_update() -> dict[str, object]:
    if not STATION_CREDENTIALS_PATH.exists():
        return {}
    try:
        data = json.loads(STATION_CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Existing device-station-credentials.json is unreadable; fix it before saving keys") from error
    if not isinstance(data, dict):
        raise ValueError("Existing device-station-credentials.json must contain a JSON object")
    return data


def station_credentials_metadata() -> list[dict[str, object]]:
    """Return profile labels and presence only; credential values never reach the browser."""
    credentials = read_station_credentials()
    result = []
    for provider, account_key, secret_keys in (
        ("ambient-weather", "ambientWeatherAccounts", ("apiKey", "applicationKey")),
        ("weather-underground", "weatherUndergroundAccounts", ("apiKey",)),
    ):
        accounts = credentials.get(account_key, {})
        if not isinstance(accounts, dict):
            continue
        for profile_id, account in accounts.items():
            if not isinstance(profile_id, str) or not isinstance(account, dict):
                continue
            result.append({
                "provider": provider,
                "id": profile_id,
                "configured": all(isinstance(account.get(key), str) and bool(account[key].strip()) for key in secret_keys),
            })
    return result


def station_settings_payload() -> dict[str, object]:
    return {
        "profiles": station_credentials_metadata(),
        "integrations": [
            {key: value for key, value in source.items() if key not in ("sourceIp",)}
            for source in _station_config.get("integrations", [])
        ],
    }


def validate_managed_station_sources(raw_sources: object) -> list[dict[str, object]]:
    if not isinstance(raw_sources, list) or len(raw_sources) > 100:
        raise ValueError("Stations must be a list of at most 100 entries")
    normalized = []
    for source in raw_sources:
        if not isinstance(source, dict):
            raise ValueError("Each station must be an object")
        allowed = {"id", "name", "provider", "connection", "credentialsId", "deviceId", "stationId", "locationId", "staleAfterSeconds"}
        if set(source) - allowed:
            raise ValueError("Station entry contains unsupported fields")
        if source.get("connection") != "cloud-api" or source.get("provider") not in ("ambient-weather", "weather-underground"):
            raise ValueError("Settings can add Ambient Weather or Weather Underground cloud stations")
        item = dict(source)
        item["enabled"] = True
        normalized.append(item)
    return normalized


def refresh_ambient_weather_cloud_once() -> None:
    """Refresh each configured Ambient Weather account once without exposing its keys."""
    global _station_source_status
    credential_file = read_station_credentials()
    cloud_sources = [source for source in _station_config.get("integrations", []) if source["provider"] == "ambient-weather" and source["connection"] == "cloud-api"]
    credentials = credential_file.get("ambientWeatherAccounts", {})
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    next_status: dict[str, str] = {}
    for source in cloud_sources:
        account = credentials.get(source["credentialsId"], {}) if isinstance(credentials, dict) else {}
        api_key = account.get("apiKey", "") if isinstance(account, dict) else ""
        application_key = account.get("applicationKey", "") if isinstance(account, dict) else ""
        if not isinstance(api_key, str) or not api_key.strip() or not isinstance(application_key, str) or not application_key.strip():
            next_status[source["id"]] = "Credentials not configured"
            continue
        groups.setdefault((api_key.strip(), application_key.strip()), []).append(source)

    for (api_key, application_key), sources in groups.items():
        query = urlencode({"apiKey": api_key, "applicationKey": application_key})
        request = Request(f"https://rt.ambientweather.net/v1/devices?{query}", headers={"User-Agent": "Dayglance/1.0"})
        try:
            with urlopen(request, timeout=12) as response:
                devices = json.loads(response.read(1_000_000))
            if not isinstance(devices, list):
                raise ValueError("Unexpected provider response")
            devices_by_mac = {
                str(device.get("macAddress", "")).replace(":", "").replace("-", "").lower(): device
                for device in devices if isinstance(device, dict)
            }
            for source in sources:
                device = devices_by_mac.get(str(source["deviceId"]).replace(":", "").replace("-", "").lower())
                if not device:
                    next_status[source["id"]] = "Station not found in Ambient Weather account"
                    continue
                data = device.get("lastData", {})
                if not isinstance(data, dict):
                    next_status[source["id"]] = "No current station reading"
                    continue
                upload = dict(data)
                epoch_ms = upload.get("dateutc")
                if isinstance(epoch_ms, (int, float)):
                    upload["dateutc"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(float(epoch_ms) / 1000))
                observation = normalize_upload(upload)
                with _station_lock:
                    _station_observations[source["id"]] = observation
                next_status[source["id"]] = "Connected to Ambient Weather"
        except HTTPError as error:
            error.close()
            safe_status = "Ambient Weather rejected the credentials" if error.code in (401, 403) else "Ambient Weather request failed"
            for source in sources:
                next_status[source["id"]] = safe_status
        except (URLError, TimeoutError, OSError, ValueError, TypeError, OverflowError):
            for source in sources:
                next_status[source["id"]] = "Ambient Weather unavailable or returned invalid data"
    with _station_lock:
        _station_source_status.update(next_status)


def refresh_weather_underground_cloud_once() -> None:
    """Fetch current observations for configured Weather Underground PWS IDs."""
    global _station_source_status
    sources = [source for source in _station_config.get("integrations", []) if source["provider"] == "weather-underground" and source["connection"] == "cloud-api"]
    if not sources:
        return
    credential_map = read_station_credentials().get("weatherUndergroundAccounts", {})
    next_status: dict[str, str] = {}
    for source in sources:
        account = credential_map.get(source["credentialsId"], {}) if isinstance(credential_map, dict) else {}
        api_key = account.get("apiKey", "") if isinstance(account, dict) else ""
        if not isinstance(api_key, str) or not api_key.strip():
            next_status[source["id"]] = "Weather Company API key not configured"
            continue
        query = urlencode({
            "stationId": source["stationId"],
            "format": "json",
            "units": "e",
            "numericPrecision": "decimal",
            "apiKey": api_key.strip(),
        })
        request = Request(f"https://api.weather.com/v2/pws/observations/current?{query}", headers={"User-Agent": "Dayglance/1.0"})
        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read(1_000_000))
            observations = payload.get("observations", []) if isinstance(payload, dict) else []
            if not isinstance(observations, list) or not observations or not isinstance(observations[0], dict):
                next_status[source["id"]] = "No current reading from Weather Underground"
                continue
            observation = normalize_weather_company_pws(observations[0])
            with _station_lock:
                _station_observations[source["id"]] = observation
            next_status[source["id"]] = "Connected to Weather Underground"
        except HTTPError as error:
            error.close()
            next_status[source["id"]] = "Weather Company rejected the key or station access" if error.code in (401, 403) else "Weather Company request failed"
        except (URLError, TimeoutError, OSError, ValueError, TypeError, OverflowError):
            next_status[source["id"]] = "Weather Company unavailable or returned invalid data"
    with _station_lock:
        _station_source_status.update(next_status)


def poll_cloud_station_data() -> None:
    """Poll configured cloud providers once a minute and reuse their latest samples."""
    while not _station_cloud_stop.is_set():
        refresh_ambient_weather_cloud_once()
        refresh_weather_underground_cloud_once()
        _station_cloud_stop.wait(60)


def start_station_cloud_poller() -> threading.Thread | None:
    # Keep an idle poller available so stations added in Settings take effect live.
    _station_cloud_stop.clear()
    thread = threading.Thread(target=poll_cloud_station_data, name="dayglance-station-cloud", daemon=True)
    thread.start()
    return thread


def station_status_payload() -> dict[str, object]:
    with _station_lock:
        observations = dict(_station_observations)
        source_status = dict(_station_source_status)
    result = []
    for source in _station_config.get("integrations", []):
        snapshot = station_freshness(observations.get(source["id"]), int(source["staleAfterSeconds"]))
        status = source_status.get(source["id"], "Waiting for first reading")
        if source["connection"] == "local-upload":
            if snapshot["fresh"]:
                status = "Receiving local uploads"
            elif snapshot["available"]:
                status = "Last local reading is stale"
        result.append({
            "id": source["id"],
            "name": source["name"],
            "locationId": source["locationId"],
            "provider": source["provider"],
            "connection": source["connection"],
            "staleAfterSeconds": source["staleAfterSeconds"],
            "status": status,
            **snapshot,
        })
    return {
        "receiverEnabled": any(source["connection"] == "local-upload" for source in _station_config.get("integrations", [])),
        "receiverStatus": _station_receiver_status,
        "integrations": result,
    }


def start_station_receiver() -> ThreadingHTTPServer | None:
    """Start a narrow inbound uploader only when explicitly enabled in config."""
    global _station_config, _station_receiver_status
    try:
        _station_config = load_station_configuration()
    except ValueError as error:
        _station_config = {"receiver": {}, "integrations": []}
        _station_receiver_status = f"error: {error}"
        print(f"Local weather-station receiver configuration is invalid: {error}")
        return None
    integrations = _station_config["integrations"]
    local_integrations = [source for source in integrations if source["connection"] == "local-upload"]
    if not local_integrations:
        _station_receiver_status = "disabled"
        return None

    by_ip = {str(source["sourceIp"]): str(source["id"]) for source in local_integrations}
    upload_path = str(_station_config["receiver"]["path"])

    class StationUploadHandler(BaseHTTPRequestHandler):
        server_version = "DayglanceStation/1.0"

        def handle_upload(self, values: dict[str, list[str]]) -> None:
            source_id = by_ip.get(self.client_address[0])
            if source_id is None:
                self.send_error(403, "Unregistered weather station")
                return
            try:
                observation = normalize_upload({key: items[-1] for key, items in values.items() if items})
            except ValueError as error:
                self.send_error(400, str(error))
                return
            with _station_lock:
                _station_observations[source_id] = observation
            body = b"success\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlsplit(self.path)
            if parsed.path != upload_path:
                self.send_error(404, "Not found")
                return
            if len(parsed.query) > 8192:
                self.send_error(413, "Station upload is too large")
                return
            try:
                values = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=64)
            except ValueError:
                self.send_error(400, "Station upload has too many fields")
                return
            self.handle_upload(values)

        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlsplit(self.path)
            if parsed.path != upload_path:
                self.send_error(404, "Not found")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 8192:
                    raise ValueError
                raw = self.rfile.read(size).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                self.send_error(400, "Invalid station upload body")
                return
            try:
                values = parse_qs(raw, keep_blank_values=True, max_num_fields=64)
            except ValueError:
                self.send_error(400, "Station upload has too many fields")
                return
            self.handle_upload(values)

        def log_message(self, format: str, *args: object) -> None:
            # Never log station requests; upload query strings may contain provider fields.
            return

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    receiver = _station_config["receiver"]
    try:
        server = ReusableThreadingHTTPServer((str(receiver["bindAddress"]), int(receiver["port"])), StationUploadHandler)
    except OSError as error:
        _station_receiver_status = f"error: {error}"
        print(f"Local weather-station receiver could not start: {error}")
        return None
    _station_receiver_status = "listening"
    return server


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, data: dict[str, object]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_device_settings(self) -> dict[str, object]:
        data: dict[str, object] = {}
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(config, dict) and isinstance(config.get("startup"), dict):
                data.update(config["startup"])
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        try:
            override = json.loads(DEVICE_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(override, dict):
                data.update(override)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return {
            "autoStart": data.get("autoStart") is True,
            "kiosk": data.get("kiosk") is not False,
            "autostartInstalled": self.autostart_is_configured(),
            "startupSupported": STARTUP_SUPPORTED,
        }

    def autostart_is_configured(self) -> bool:
        if "labwc" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
            path = Path.home() / ".config" / "labwc" / "autostart"
            try:
                return "# Dayglance managed startup" in path.read_text(encoding="utf-8")
            except OSError:
                return False
        return AUTOSTART_PATH.is_file()

    def ensure_autostart_entry(self) -> None:
        """Create the desktop login dispatcher once, when local settings are saved."""
        launcher = shlex.quote(str(ROOT / "launch-dayglance.sh"))
        if "labwc" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
            path = Path.home() / ".config" / "labwc" / "autostart"
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                current = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                current = ""
            if "# Dayglance managed startup" in current:
                return
            addition = f"# Dayglance managed startup\n/bin/sh {launcher} &\n"
            with path.open("a", encoding="utf-8") as stream:
                if current and not current.endswith("\n"):
                    stream.write("\n")
                if current:
                    stream.write("\n")
                stream.write(addition)
            return
        if AUTOSTART_PATH.is_file():
            return
        AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
        escaped_launcher = str(ROOT / "launch-dayglance.sh").replace("\\", "\\\\").replace('"', '\\"')
        desktop_entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Dayglance\n"
            "Comment=Start the Dayglance weather display at desktop login\n"
            f'Exec="/bin/sh" "{escaped_launcher}"\n'
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        temporary = AUTOSTART_PATH.with_name(f".{AUTOSTART_PATH.name}.tmp")
        try:
            temporary.write_text(desktop_entry, encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(AUTOSTART_PATH)
        except OSError:
            temporary.unlink(missing_ok=True)
            raise

    def is_local_client(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0].split("%", maxsplit=1)[0]).is_loopback
        except ValueError:
            return False

    def is_local_app_request(self) -> bool:
        origin = self.headers.get("Origin")
        return self.is_local_client() and (not origin or urlsplit(origin).netloc == self.headers.get("Host"))

    def radar_provider_guard(self) -> bool:
        if self.is_local_app_request():
            return True
        self.send_error(403, "Radar provider access is restricted to the local Dayglance display")
        return False

    def upstream_response(self, url: str, *, api_key: str | None = None) -> tuple[int, str, bytes]:
        headers = {"User-Agent": "Dayglance/1.0"}
        if api_key:
            headers["Ocp-Apim-Subscription-Key"] = api_key
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=12) as response:
                return response.status, response.headers.get_content_type(), response.read(4_000_000)
        except HTTPError as error:
            error.close()
            return error.code, "application/json", b"{}"
        except (URLError, TimeoutError, OSError):
            return 502, "application/json", b'{"error":"Weather radar provider is unavailable"}'

    def send_upstream(self, url: str, *, api_key: str | None = None, usage_kind: str | None = None, radar_provider: str | None = None) -> None:
        status, content_type, body = self.upstream_response(url, api_key=api_key)
        if radar_provider:
            record_provider_health(radar_provider, status)
        if status == 200 and usage_kind:
            try:
                record_rainbow_usage(usage_kind)
            except OSError:
                pass
        self.send_response(status if status < 400 else 502)
        self.send_header("Content-Type", content_type if status == 200 else "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def rainbow_url(self, endpoint: str, params: dict[str, str] | None = None) -> str | None:
        api_key = read_radar_key()
        if not api_key:
            self.send_json(503, {"error": "Add a Rainbow Weather API key in Settings to enable forecast radar."})
            return None
        query = dict(params or {})
        query["token"] = api_key
        return f"{RAINBOW_BASE}/{endpoint}?{urlencode(query)}"

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        requested = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
        if requested == "api/station-settings":
            if not self.is_local_app_request():
                self.send_error(403, "Station settings are restricted to the local Dayglance display")
                return
            self.send_json(200, station_settings_payload())
            return
        if requested == "api/weather-alerts":
            if not self.is_local_app_request():
                self.send_error(403, "Weather alerts are restricted to the local Dayglance display")
                return
            try:
                params = parse_qs(urlsplit(self.path).query, max_num_fields=4)
                latitude = float(params["latitude"][0])
                longitude = float(params["longitude"][0])
                if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
                    raise ValueError
            except (KeyError, IndexError, TypeError, ValueError):
                self.send_json(400, {"error": "Valid latitude and longitude are required"})
                return
            try:
                self.send_json(200, active_alerts_for_point(latitude, longitude))
            except OSError as error:
                self.send_json(502, {"error": str(error)})
            return
        if requested == "api/local-stations":
            if not self.is_local_app_request():
                self.send_error(403, "Station readings are restricted to the local Dayglance display")
                return
            self.send_json(200, station_status_payload())
            return
        if requested == "api/device-settings":
            self.send_json(200, self.read_device_settings())
            return
        if requested == "api/radar/status":
            usage = current_usage()
            self.send_json(200, {
                "configured": bool(read_radar_key()),
                "canManage": self.is_local_app_request(),
                "usage": usage,
                "remaining": {
                    "tiles": max(0, int(usage["tileAllowance"]) - int(usage["tiles"])),
                    "nowcast": max(0, int(usage["nowcastAllowance"]) - int(usage["nowcast"])),
                },
                "providers": provider_health_snapshot(),
            })
            return
        if requested == "api/radar/rainviewer-metadata":
            if self.radar_provider_guard():
                self.send_upstream(RAINVIEWER_METADATA, radar_provider="rainviewer")
            return
        if requested == "api/radar/rainbow-snapshot":
            if not self.radar_provider_guard():
                return
            url = self.rainbow_url("tiles/v1/snapshot")
            if url:
                self.send_upstream(url, api_key=read_radar_key(), radar_provider="rainbow")
            return
        if requested.startswith("api/radar/rainbow-tile/"):
            if not self.radar_provider_guard():
                return
            parts = requested.removeprefix("api/radar/rainbow-tile/").split("/")
            if len(parts) != 5 or not all(part.isdigit() for part in parts):
                self.send_error(400, "Invalid radar tile coordinates")
                return
            snapshot, forecast_time, zoom, x, y = map(int, parts)
            if not 0 <= zoom <= 12 or forecast_time < 0 or forecast_time > 14400 or forecast_time % 600:
                self.send_error(400, "Invalid radar forecast frame")
                return
            if x >= 2**zoom or y >= 2**zoom:
                self.send_error(400, "Invalid radar tile coordinates")
                return
            usage = current_usage()
            if not usage["allowPaidUsage"] and int(usage["tiles"]) >= int(usage["tileAllowance"]):
                self.send_json(429, {"error": "This device reached the Rainbow free tile allowance. Enable pay-as-you-go in local Dayglance Settings to continue."})
                return
            endpoint = f"tiles/v1/precip/{snapshot}/{forecast_time}/{zoom}/{x}/{y}"
            url = self.rainbow_url(endpoint, {"coverage": "1"})
            if url:
                self.send_upstream(url, api_key=read_radar_key(), usage_kind="tiles", radar_provider="rainbow")
            return
        if requested.startswith("api/radar/rainbow-nowcast/"):
            if not self.radar_provider_guard():
                return
            parts = requested.removeprefix("api/radar/rainbow-nowcast/").split("/")
            if len(parts) != 2:
                self.send_error(400, "Invalid location coordinates")
                return
            try:
                longitude, latitude = map(float, parts)
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError
            except ValueError:
                self.send_error(400, "Invalid location coordinates")
                return
            endpoint = f"nowcast/v1/precip/{longitude}/{latitude}"
            url = self.rainbow_url(endpoint)
            if url:
                self.send_upstream(url, api_key=read_radar_key(), usage_kind="nowcast", radar_provider="rainbow")
            return
        mime_type = FILES.get(requested)
        if mime_type is None:
            self.send_error(404, "File not found")
            return

        try:
            body = (ROOT / requested).read_bytes()
        except OSError:
            self.send_error(404, "File not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        requested = unquote(urlsplit(self.path).path).lstrip("/")
        if requested == "api/station-settings":
            self.handle_station_settings()
            return
        if requested == "api/station-credentials":
            self.handle_station_credentials()
            return
        if requested == "api/radar/credential":
            self.handle_radar_credential()
            return
        if requested == "api/radar/paid-usage":
            self.handle_paid_usage_setting()
            return
        if requested != "api/device-settings":
            self.send_error(404, "File not found")
            return
        origin = self.headers.get("Origin")
        if not self.is_local_client() or (origin and urlsplit(origin).netloc != self.headers.get("Host")):
            self.send_error(403, "Device settings can only be changed from this Pi")
            return
        if not STARTUP_SUPPORTED:
            self.send_error(501, "Desktop login startup is supported on Linux only")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "Expected application/json")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 4096:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or set(data) != {"autoStart", "kiosk"}:
                raise ValueError("Expected autoStart and kiosk settings")
            if not all(isinstance(data[key], bool) for key in ("autoStart", "kiosk")):
                raise ValueError("Settings must be true or false")
        except (ValueError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))
            return

        if data["autoStart"]:
            try:
                self.ensure_autostart_entry()
            except OSError:
                self.send_error(500, "Could not install the desktop login entry")
                return

        temporary = DEVICE_SETTINGS_PATH.with_name(f".{DEVICE_SETTINGS_PATH.name}.tmp")
        try:
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            if os.name == "posix":
                temporary.chmod(0o600)
            temporary.replace(DEVICE_SETTINGS_PATH)
        except OSError:
            temporary.unlink(missing_ok=True)
            self.send_error(500, "Could not save device settings")
            return
        self.send_json(200, self.read_device_settings())

    def read_local_json_body(self, maximum: int) -> dict[str, object] | None:
        if not self.is_local_app_request():
            self.send_error(403, "Station settings can only be changed from the local Dayglance display")
            return None
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "Expected application/json")
            return None
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > maximum:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            return data
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
            return None

    def handle_station_settings(self) -> None:
        data = self.read_local_json_body(65536)
        if data is None:
            return
        if set(data) != {"integrations"}:
            self.send_json(400, {"error": "Expected the integrations list"})
            return
        try:
            integrations = validate_managed_station_sources(data["integrations"])
            validated = load_station_configuration(managed_override=integrations)
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
            return
        try:
            write_private_json(STATION_SETTINGS_PATH, {"integrations": integrations})
        except OSError:
            self.send_json(500, {"error": "Could not save station settings on this device."})
            return
        global _station_config
        previous_sources = {source["id"]: source for source in _station_config.get("integrations", [])}
        _station_config = validated
        active_ids = {str(source["id"]) for source in validated["integrations"]}
        changed_ids = {
            source_id for source_id, source in {item["id"]: item for item in validated["integrations"]}.items()
            if source_id in previous_sources and any(previous_sources[source_id].get(key) != source.get(key) for key in ("provider", "connection", "deviceId", "stationId", "credentialsId"))
        }
        with _station_lock:
            for source_id in (set(_station_observations) - active_ids) | changed_ids:
                _station_observations.pop(source_id, None)
                _station_source_status.pop(source_id, None)
        self.send_json(200, station_settings_payload())

    def handle_station_credentials(self) -> None:
        data = self.read_local_json_body(8192)
        if data is None:
            return
        provider = data.get("provider")
        profile_id = data.get("id")
        if provider not in ("ambient-weather", "weather-underground") or not isinstance(profile_id, str) or not 1 <= len(profile_id.strip()) <= 80 or any(not (char.isalnum() or char in "-_ ") for char in profile_id):
            self.send_json(400, {"error": "Choose a short profile name using letters, numbers, spaces, hyphens or underscores."})
            return
        required = ("apiKey", "applicationKey") if provider == "ambient-weather" else ("apiKey",)
        if set(data) != {"provider", "id", *required}:
            self.send_json(400, {"error": "Provide all required key fields for this provider."})
            return
        secrets = {key: data.get(key) for key in required}
        if any(not isinstance(value, str) or not 8 <= len(value.strip()) <= 512 for value in secrets.values()):
            self.send_json(400, {"error": "Enter each provider key (8 to 512 characters)."})
            return
        try:
            credentials = station_credentials_for_update()
        except ValueError as error:
            self.send_json(409, {"error": str(error)})
            return
        account_key = "ambientWeatherAccounts" if provider == "ambient-weather" else "weatherUndergroundAccounts"
        accounts = credentials.get(account_key, {})
        if not isinstance(accounts, dict):
            accounts = {}
        accounts[profile_id.strip()] = {key: value.strip() for key, value in secrets.items()}
        credentials[account_key] = accounts
        try:
            write_private_json(STATION_CREDENTIALS_PATH, credentials)
        except OSError:
            self.send_json(500, {"error": "Could not save provider keys on this device."})
            return
        self.send_json(200, {"profiles": station_credentials_metadata(), "saved": True})

    def handle_station_credential_delete(self, profile_path: str) -> None:
        if not self.is_local_app_request():
            self.send_error(403, "Station credentials can only be managed from the local Dayglance display")
            return
        parts = profile_path.split("/", 1)
        if len(parts) != 2 or parts[0] not in ("ambient-weather", "weather-underground") or not parts[1]:
            self.send_error(400, "Invalid provider profile")
            return
        provider, profile_id = parts
        if any(source.get("credentialsId") == profile_id and source.get("provider") == provider for source in _station_config.get("integrations", [])):
            self.send_json(409, {"error": "Remove or reassign stations that use this profile first."})
            return
        try:
            credentials = station_credentials_for_update()
        except ValueError as error:
            self.send_json(409, {"error": str(error)})
            return
        account_key = "ambientWeatherAccounts" if provider == "ambient-weather" else "weatherUndergroundAccounts"
        accounts = credentials.get(account_key, {})
        if not isinstance(accounts, dict) or profile_id not in accounts:
            self.send_error(404, "Provider profile not found")
            return
        accounts.pop(profile_id, None)
        credentials[account_key] = accounts
        try:
            write_private_json(STATION_CREDENTIALS_PATH, credentials)
        except OSError:
            self.send_json(500, {"error": "Could not remove provider keys from this device."})
            return
        self.send_json(200, {"profiles": station_credentials_metadata(), "removed": True})

    def handle_radar_credential(self) -> None:
        if not self.is_local_app_request():
            self.send_error(403, "Radar credentials can only be managed from the local Dayglance display")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "Expected application/json")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 2048:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(size))
            api_key = data.get("apiKey", "") if isinstance(data, dict) else ""
            if not isinstance(api_key, str) or not 20 <= len(api_key.strip()) <= 512:
                raise ValueError("Enter a valid Rainbow Weather API key")
            api_key = api_key.strip()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))
            return

        validation_url = f"{RAINBOW_BASE}/tiles/v1/snapshot"
        status, _, body = self.upstream_response(f"{validation_url}?{urlencode({'token': api_key})}")
        if status != 200:
            record_provider_health("rainbow", status)
            self.send_json(400, {"error": "Rainbow did not accept this API key. Check it in your Rainbow developer account and try again."})
            return
        try:
            snapshot = json.loads(body)
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("snapshot"), int):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            record_provider_health("rainbow", 502)
            self.send_json(502, {"error": "Rainbow returned an unexpected response while validating the key."})
            return
        record_provider_health("rainbow", 200)
        try:
            write_private_json(RADAR_CREDENTIALS_PATH, {"rainbowApiKey": api_key})
        except OSError:
            self.send_json(500, {"error": "Could not save the API key on this device."})
            return
        self.send_json(200, {"configured": True, "usage": current_usage()})

    def handle_paid_usage_setting(self) -> None:
        if not self.is_local_app_request():
            self.send_error(403, "Paid radar usage can only be changed from the local Dayglance display")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415, "Expected application/json")
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 1024:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or set(data) != {"allowPaidUsage"}:
                raise ValueError("Expected allowPaidUsage true or false")
            enabled = data["allowPaidUsage"]
            if not isinstance(enabled, bool):
                raise ValueError("Expected allowPaidUsage true or false")
            if enabled and not read_radar_key():
                self.send_json(409, {"error": "Add and validate your Rainbow API key before enabling pay-as-you-go."})
                return
        except (ValueError, json.JSONDecodeError) as error:
            self.send_error(400, str(error))
            return
        try:
            save_paid_usage_setting(enabled)
        except OSError:
            self.send_json(500, {"error": "Could not save the paid-usage preference on this device."})
            return
        self.send_json(200, {"configured": bool(read_radar_key()), "usage": current_usage()})

    def do_DELETE(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        requested = unquote(urlsplit(self.path).path).lstrip("/")
        if requested.startswith("api/station-credentials/"):
            self.handle_station_credential_delete(requested.removeprefix("api/station-credentials/"))
            return
        if requested != "api/radar/credential":
            self.send_error(404, "File not found")
            return
        if not self.is_local_app_request():
            self.send_error(403, "Radar credentials can only be managed from the local Dayglance display")
            return
        had_key = bool(read_radar_key())
        try:
            RADAR_CREDENTIALS_PATH.unlink(missing_ok=True)
            if had_key:
                save_paid_usage_setting(False)
        except OSError:
            self.send_json(500, {"error": "Could not remove the API key from this device."})
            return
        self.send_json(200, {"configured": False})

    def log_message(self, format: str, *args: object) -> None:
        if len(args) > 1 and str(args[1]).isdigit() and int(args[1]) < 400:
            return
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Dayglance on a local network.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", default=8080, type=int, help="port (default: 8080)")
    args = parser.parse_args()

    load_radar_usage()
    station_server = start_station_receiver()
    station_cloud_thread = start_station_cloud_poller()
    station_thread = None
    if station_server is not None:
        station_thread = threading.Thread(target=station_server.serve_forever, name="dayglance-local-station", daemon=True)
        station_thread.start()
        print(f"Local weather-station receiver listening at http://{station_server.server_address[0]}:{station_server.server_address[1]}")
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Dayglance is available at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Dayglance server.")
    finally:
        server.server_close()
        if station_server is not None:
            station_server.shutdown()
            station_server.server_close()
            if station_thread is not None:
                station_thread.join(timeout=2)
        if station_cloud_thread is not None:
            _station_cloud_stop.set()
            station_cloud_thread.join(timeout=2)
        try:
            flush_radar_usage()
        except OSError:
            print("Could not persist the latest local radar usage estimate.")


if __name__ == "__main__":
    main()
