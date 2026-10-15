#!/usr/bin/env python3
"""Small standard-library server for the Dayglance static app."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
DEVICE_SETTINGS_PATH = ROOT / "device-settings.json"
CONFIG_PATH = ROOT / "config.json"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "dayglance.desktop"
FILES = {
    "index.html": "text/html; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "manifest.webmanifest": "application/manifest+json; charset=utf-8",
    "config.json": "application/json; charset=utf-8",
    "sw.js": "text/javascript; charset=utf-8",
}


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
            "autostartInstalled": AUTOSTART_PATH.is_file(),
        }

    def is_local_client(self) -> bool:
        try:
            return ipaddress.ip_address(self.client_address[0].split("%", maxsplit=1)[0]).is_loopback
        except ValueError:
            return False

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        requested = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
        if requested == "api/device-settings":
            self.send_json(200, self.read_device_settings())
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
        if requested != "api/device-settings":
            self.send_error(404, "File not found")
            return
        origin = self.headers.get("Origin")
        if not self.is_local_client() or (origin and urlsplit(origin).netloc != self.headers.get("Host")):
            self.send_error(403, "Device settings can only be changed from this Pi")
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

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Dayglance on a local network.")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", default=8080, type=int, help="port (default: 8080)")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    print(f"Dayglance is available at http://{args.host}:{args.port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Dayglance server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
