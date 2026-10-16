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
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, unquote, urlsplit
from urllib.request import Request, urlopen


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
    "location-order.js": "text/javascript; charset=utf-8",
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
    server = HTTPServer((args.host, args.port), Handler)
    print(f"Dayglance is available at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Dayglance server.")
    finally:
        server.server_close()
        try:
            flush_radar_usage()
        except OSError:
            print("Could not persist the latest local radar usage estimate.")


if __name__ == "__main__":
    main()
