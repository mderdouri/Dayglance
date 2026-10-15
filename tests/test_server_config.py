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
        cls.autostart_path = root / "autostart" / "dayglance.desktop"
        cls.labwc_autostart_path = cls.home / ".config" / "labwc" / "autostart"
        cls.patches = [
            patch.object(server, "CONFIG_PATH", cls.config_path),
            patch.object(server, "DEVICE_SETTINGS_PATH", cls.settings_path),
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
        self.autostart_path.unlink(missing_ok=True)
        self.labwc_autostart_path.unlink(missing_ok=True)

    def request(self, data=None):
        headers = {"Content-Type": "application/json", "Origin": self.base.rstrip("/")} if data is not None else {}
        request = Request(self.base + "api/device-settings", data=data, headers=headers, method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            try:
                return error.code, error.read()
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


if __name__ == "__main__":
    unittest.main(verbosity=2)

