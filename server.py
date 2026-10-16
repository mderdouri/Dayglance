#!/usr/bin/env python3
"""Small standard-library server for the Dayglance static app."""

from __future__ import annotations

import argparse
import ipaddress
import json
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

from weather_station import freshness as station_freshness, normalize_upload


ROOT = Path(__file__).resolve().parent
DEVICE_SETTINGS_PATH = ROOT / "device-settings.json"
RADAR_CREDENTIALS_PATH = ROOT / "device-radar-key.json"
RADAR_USAGE_PATH = ROOT / "device-radar-usage.json"
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
USAGE_FLUSH_SECONDS = 3600
_usage_lock = threading.Lock()
_usage_state: dict[str, object] = {"month": "", "tiles": 0, "nowcast": 0, "allowPaidUsage": False}
_usage_last_write = 0.0
_station_lock = threading.Lock()
_station_observations: dict[str, dict[str, object]] = {}
_station_config: dict[str, object] = {"receiver": {}, "integrations": []}
_station_receiver_status = "disabled"


def read_radar_key() -> str:
    try:
        data = json.loads(RADAR_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return data.get("rainbowApiKey", "") if isinstance(data, dict) else ""
    except (OSError, ValueError, json.JSONDecodeError):
        return ""


def write_private_json(path: Path, data: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        if os.name == "posix":
            temporary.chmod(0o600)
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


def load_station_configuration() -> dict[str, object]:
    """Read and validate city-scoped local station upload definitions."""
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        config = {}
    raw_receiver = config.get("stationReceiver", {}) if isinstance(config, dict) else {}
    raw_sources = config.get("stationIntegrations", []) if isinstance(config, dict) else []
    if not isinstance(raw_receiver, dict) or not isinstance(raw_sources, list):
        raise ValueError("stationReceiver must be an object and stationIntegrations must be an array")

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
        if source.get("provider") != "ambient-weather" or source.get("connection") != "local-upload":
            raise ValueError(f"Unsupported station adapter for {source_id!r}; currently use ambient-weather/local-upload")
        try:
            source_ip = ipaddress.ip_address(str(source.get("sourceIp", "")))
            bind_ip = ipaddress.ip_address(str(receiver["bindAddress"]))
            port = int(receiver["port"])
            stale_after = int(source.get("staleAfterSeconds", 600))
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid network or timeout setting for station {source_id!r}") from error
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
        if not 30 <= stale_after <= 3600:
            raise ValueError(f"Station {source_id!r} staleAfterSeconds must be between 30 and 3600")
        integrations.append({
            "id": source_id,
            "name": str(source.get("name") or "Local weather station")[:80],
            "locationId": location_id,
            "sourceIp": str(source_ip),
            "provider": "ambient-weather",
            "connection": "local-upload",
            "staleAfterSeconds": stale_after,
        })

    return {"receiver": receiver, "integrations": integrations}


def station_status_payload() -> dict[str, object]:
    with _station_lock:
        observations = dict(_station_observations)
    result = []
    for source in _station_config.get("integrations", []):
        snapshot = station_freshness(observations.get(source["id"]), int(source["staleAfterSeconds"]))
        result.append({
            "id": source["id"],
            "name": source["name"],
            "locationId": source["locationId"],
            "provider": source["provider"],
            "connection": source["connection"],
            "staleAfterSeconds": source["staleAfterSeconds"],
            **snapshot,
        })
    return {
        "receiverEnabled": bool(_station_config.get("integrations")),
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
    if not integrations:
        _station_receiver_status = "disabled"
        return None

    by_ip = {str(source["sourceIp"]): str(source["id"]) for source in integrations}
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

    def send_upstream(self, url: str, *, api_key: str | None = None, usage_kind: str | None = None) -> None:
        status, content_type, body = self.upstream_response(url, api_key=api_key)
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
            })
            return
        if requested == "api/radar/rainviewer-metadata":
            if self.radar_provider_guard():
                self.send_upstream(RAINVIEWER_METADATA)
            return
        if requested == "api/radar/rainbow-snapshot":
            if not self.radar_provider_guard():
                return
            url = self.rainbow_url("tiles/v1/snapshot")
            if url:
                self.send_upstream(url, api_key=read_radar_key())
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
                self.send_upstream(url, api_key=read_radar_key(), usage_kind="tiles")
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
                self.send_upstream(url, api_key=read_radar_key(), usage_kind="nowcast")
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
            self.send_json(400, {"error": "Rainbow did not accept this API key. Check it in your Rainbow developer account and try again."})
            return
        try:
            snapshot = json.loads(body)
            if not isinstance(snapshot, dict) or not isinstance(snapshot.get("snapshot"), int):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            self.send_json(502, {"error": "Rainbow returned an unexpected response while validating the key."})
            return
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
        try:
            flush_radar_usage()
        except OSError:
            print("Could not persist the latest local radar usage estimate.")


if __name__ == "__main__":
    main()
