"""Integration tests for device startup settings and config.json precedence."""

import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
import server  # noqa: E402


class DeviceSettingsConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="dayglance-config-api-")
        root = Path(cls.temp.name)
        cls.home = root / "home"
        cls.home.mkdir()
        cls.config_path = root / "config.json"
        cls.settings_path = root / "device-settings.json"
        cls.radar_key_path = root / "device-radar-key.json"
        cls.radar_usage_path = root / "device-radar-usage.json"
        cls.autostart_path = root / "autostart" / "dayglance.desktop"
        cls.labwc_autostart_path = cls.home / ".config" / "labwc" / "autostart"
        cls.patches = [
            patch.object(server, "CONFIG_PATH", cls.config_path),
            patch.object(server, "DEVICE_SETTINGS_PATH", cls.settings_path),
            patch.object(server, "RADAR_CREDENTIALS_PATH", cls.radar_key_path),
            patch.object(server, "RADAR_USAGE_PATH", cls.radar_usage_path),
            patch.object(server, "AUTOSTART_PATH", cls.autostart_path),
            patch.object(server, "STARTUP_SUPPORTED", True),
            patch.dict("os.environ", {"HOME": str(cls.home), "XDG_CURRENT_DESKTOP": "labwc:wlroots"}),
        ]
        for item in cls.patches:
            item.start()
        cls.httpd = HTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}/"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.thread.join(timeout=2)
        cls.httpd.server_close()
        for item in reversed(cls.patches):
            item.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.config_path.write_text(json.dumps({"startup": {"autoStart": False, "kiosk": True}}), encoding="utf-8")
        self.settings_path.unlink(missing_ok=True)
        self.radar_key_path.unlink(missing_ok=True)
        self.radar_usage_path.unlink(missing_ok=True)
        server._usage_state.update({"month": "", "tiles": 0, "nowcast": 0, "allowPaidUsage": False})
        server._usage_last_write = 0.0
        self.autostart_path.unlink(missing_ok=True)
        self.labwc_autostart_path.unlink(missing_ok=True)

    def request(self, data=None, *, path="api/device-settings", method=None):
        actual_method = method or ("POST" if data is not None else "GET")
        headers = {"Origin": self.base.rstrip("/")} if actual_method != "GET" else {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self.base + path, data=data, headers=headers, method=actual_method)
        try:
            with urlopen(request, timeout=3) as response:
                body = response.read()
                try:
                    return response.status, json.loads(body)
                except (ValueError, json.JSONDecodeError):
                    return response.status, body
        except HTTPError as error:
            try:
                body = error.read()
                try:
                    return error.code, json.loads(body)
                except (ValueError, json.JSONDecodeError):
                    return error.code, body
            finally:
                error.close()

    def test_get_uses_startup_defaults_from_config(self):
        self.config_path.write_text(json.dumps({"startup": {"autoStart": True, "kiosk": False}}), encoding="utf-8")
        self.assertEqual(self.request(), (200, {"autoStart": True, "kiosk": False, "autostartInstalled": False, "startupSupported": True}))

    def test_air_quality_helper_is_served_as_javascript(self):
        with urlopen(self.base + "air-quality.js", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("text/javascript", response.headers["Content-Type"])
            self.assertIn("DayglanceAirQuality", response.read().decode("utf-8"))

    def test_station_provider_options_are_visible_in_settings_page(self):
        with urlopen(self.base + "index.html", timeout=3) as response:
            self.assertEqual(response.status, 200)
            page = response.read().decode("utf-8")
        settings = page.split('id="station-settings"', 1)[1].split("</section>", 1)[0]
        self.assertNotIn("hidden", settings.split(">", 1)[0])
        providers = settings.split('<div class="station-supported-options"', 1)[1].split('<div id="station-integrations-list"', 1)[0]
        self.assertIn("Ambient Weather", providers)
        self.assertIn("Local upload · Cloud API", providers)
        self.assertIn("Weather Underground PWS", providers)
        self.assertIn("Config file · read-only", providers)
        self.assertIn("Reference only—these are not input fields", providers)
        self.assertNotIn("<input", providers)
        self.assertNotIn("<select", providers)
        self.assertNotIn("<button", providers)
        self.assertIn("device-station-credentials.json", settings)

    def test_hourly_scroll_bumpers_are_disabled_by_default(self):
        project_config = json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))
        with urlopen(self.base + "index.html", timeout=3) as response:
            page = response.read().decode("utf-8")
        app = (PROJECT_ROOT / "app.js").read_text(encoding="utf-8")
        self.assertFalse(project_config["preferences"]["showBumpers"])
        self.assertIn("showBumpers:false", app)
        self.assertIn('id="setting-bumpers" type="checkbox"', page)
        self.assertNotIn('id="setting-bumpers" type="checkbox" checked', page)

    def test_device_file_overrides_config_defaults(self):
        self.config_path.write_text(json.dumps({"startup": {"autoStart": True, "kiosk": False}}), encoding="utf-8")
        self.settings_path.write_text(json.dumps({"autoStart": False, "kiosk": True}), encoding="utf-8")
        self.assertEqual(self.request(), (200, {"autoStart": False, "kiosk": True, "autostartInstalled": False, "startupSupported": True}))

    def test_settings_ui_post_persists_local_override(self):
        self.config_path.write_text(json.dumps({"startup": {"autoStart": False, "kiosk": True}}), encoding="utf-8")
        payload = json.dumps({"autoStart": True, "kiosk": False}).encode("utf-8")
        self.assertEqual(self.request(payload), (200, {"autoStart": True, "kiosk": False, "autostartInstalled": True, "startupSupported": True}))
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8")), {"autoStart": True, "kiosk": False})
        labwc_config = self.labwc_autostart_path.read_text(encoding="utf-8")
        self.assertIn("# Dayglance managed startup", labwc_config)
        self.assertIn("launch-dayglance.sh", labwc_config)
        self.assertTrue(labwc_config.endswith("\n"))

    def test_non_labwc_session_installs_desktop_entry(self):
        with patch.dict("os.environ", {"XDG_CURRENT_DESKTOP": "GNOME"}):
            handler = object.__new__(server.Handler)
            handler.ensure_autostart_entry()
        desktop_entry = self.autostart_path.read_text(encoding="utf-8")
        self.assertIn("X-GNOME-Autostart-enabled=true", desktop_entry)
        self.assertTrue(desktop_entry.endswith("\n"))

    def test_labwc_hook_preserves_existing_entries_and_is_idempotent(self):
        self.labwc_autostart_path.parent.mkdir(parents=True, exist_ok=True)
        self.labwc_autostart_path.write_text("# Existing desktop command\nexisting-command &\n", encoding="utf-8")
        handler = object.__new__(server.Handler)
        handler.ensure_autostart_entry()
        handler.ensure_autostart_entry()
        labwc_config = self.labwc_autostart_path.read_text(encoding="utf-8")
        self.assertTrue(labwc_config.startswith("# Existing desktop command\nexisting-command &\n"))
        self.assertEqual(labwc_config.count("# Dayglance managed startup"), 1)

    def test_startup_settings_reject_unsupported_platforms(self):
        payload = json.dumps({"autoStart": True, "kiosk": True}).encode("utf-8")
        with patch.object(server, "STARTUP_SUPPORTED", False):
            self.assertEqual(self.request(payload)[0], 501)
        self.assertFalse(self.settings_path.exists())
        self.assertFalse(self.labwc_autostart_path.exists())

    def test_invalid_config_falls_back_to_safe_startup_defaults(self):
        self.config_path.write_text("not-json", encoding="utf-8")
        self.assertEqual(self.request(), (200, {"autoStart": False, "kiosk": True, "autostartInstalled": False, "startupSupported": True}))

    def test_successful_requests_are_not_written_to_server_log(self):
        handler = object.__new__(server.Handler)
        output = io.StringIO()
        with patch.object(server.Handler, "address_string", return_value="127.0.0.1"):
            with redirect_stdout(output):
                server.Handler.log_message(handler, '"%s" %s %s', "GET /app.js HTTP/1.1", 200, "100")
        self.assertEqual(output.getvalue(), "")

    def test_failed_requests_remain_visible_in_server_log(self):
        handler = object.__new__(server.Handler)
        output = io.StringIO()
        with patch.object(server.Handler, "address_string", return_value="127.0.0.1"):
            with redirect_stdout(output):
                server.Handler.log_message(handler, '"%s" %s %s', "GET /missing HTTP/1.1", 404, "0")
        self.assertIn("404", output.getvalue())

    def test_radar_status_reports_device_allowance_without_returning_key(self):
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key-01"}), encoding="utf-8")
        status, data = self.request(path="api/radar/status")
        self.assertEqual(status, 200)
        self.assertTrue(data["configured"])
        self.assertFalse(data["usage"]["allowPaidUsage"])
        self.assertEqual(data["usage"]["tileAllowance"], 30000)
        self.assertEqual(data["remaining"]["tiles"], 30000)
        self.assertNotIn("not-a-real-test-key-01", json.dumps(data))

    def test_rainbow_key_is_validated_and_saved_outside_browser_response(self):
        payload = json.dumps({"apiKey": "not-a-real-test-key-01"}).encode("utf-8")
        with patch.object(server.Handler, "upstream_response", return_value=(200, "application/json", b'{"snapshot":123}')):
            status, data = self.request(payload, path="api/radar/credential")
        self.assertEqual(status, 200)
        self.assertTrue(data["configured"])
        self.assertNotIn("not-a-real-test-key-01", json.dumps(data))
        self.assertEqual(json.loads(self.radar_key_path.read_text(encoding="utf-8"))["rainbowApiKey"], "not-a-real-test-key-01")

    def test_invalid_rainbow_key_is_not_persisted(self):
        payload = json.dumps({"apiKey": "not-valid"}).encode("utf-8")
        status, _ = self.request(payload, path="api/radar/credential")
        self.assertEqual(status, 400)
        self.assertFalse(self.radar_key_path.exists())

    def test_successful_rainbow_tile_proxy_calls_are_counted(self):
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key"}), encoding="utf-8")
        with patch.object(server.Handler, "upstream_response", return_value=(200, "image/png", b"png-tile")):
            status, body = self.request(path="api/radar/rainbow-tile/1791889800/600/3/2/4")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"png-tile")
        self.assertEqual(server.current_usage()["tiles"], 1)

    def test_invalid_rainbow_tile_coordinates_are_rejected(self):
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key"}), encoding="utf-8")
        status, _ = self.request(path="api/radar/rainbow-tile/1791889800/601/3/2/4")
        self.assertEqual(status, 400)

    def test_rainbow_key_can_be_removed_from_the_device(self):
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key"}), encoding="utf-8")
        status, data = self.request(path="api/radar/credential", method="DELETE")
        self.assertEqual(status, 200)
        self.assertFalse(data["configured"])
        self.assertFalse(self.radar_key_path.exists())

    def test_rainbow_proxy_persists_local_usage_estimate(self):
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key"}), encoding="utf-8")
        with patch.object(server, "USAGE_FLUSH_SECONDS", 0), patch.object(server.Handler, "upstream_response", return_value=(200, "image/png", b"png-tile")):
            status, _ = self.request(path="api/radar/rainbow-tile/1791889800/600/3/2/4")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(self.radar_usage_path.read_text(encoding="utf-8"))["tiles"], 1)

    def test_radar_key_management_rejects_remote_clients(self):
        payload = json.dumps({"apiKey": "not-a-real-test-key"}).encode("utf-8")
        with patch.object(server.Handler, "is_local_app_request", return_value=False):
            status, _ = self.request(payload, path="api/radar/credential")
        self.assertEqual(status, 403)
        self.assertFalse(self.radar_key_path.exists())

    def test_paid_usage_requires_a_registered_key_and_is_off_by_default(self):
        payload = json.dumps({"allowPaidUsage": True}).encode("utf-8")
        status, _ = self.request(payload, path="api/radar/paid-usage")
        self.assertEqual(status, 409)
        self.assertFalse(server.current_usage()["allowPaidUsage"])
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key"}), encoding="utf-8")
        status, data = self.request(payload, path="api/radar/paid-usage")
        self.assertEqual(status, 200)
        self.assertTrue(data["usage"]["allowPaidUsage"])
        self.assertTrue(json.loads(self.radar_usage_path.read_text(encoding="utf-8"))["allowPaidUsage"])

    def test_free_tier_guard_blocks_tiles_at_the_local_allowance(self):
        self.radar_key_path.write_text(json.dumps({"rainbowApiKey": "not-a-real-test-key"}), encoding="utf-8")
        server.current_usage()
        server._usage_state.update({"tiles": 30000, "allowPaidUsage": False})
        with patch.object(server.Handler, "upstream_response") as upstream:
            status, data = self.request(path="api/radar/rainbow-tile/1791889800/600/3/2/4")
        self.assertEqual(status, 429)
        self.assertIn("free tile allowance", data["error"])
        upstream.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
