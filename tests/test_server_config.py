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
        cls.config_path = root / "config.json"
        cls.settings_path = root / "device-settings.json"
        cls.autostart_path = root / "autostart" / "dayglance.desktop"
        cls.patches = [
            patch.object(server, "CONFIG_PATH", cls.config_path),
            patch.object(server, "DEVICE_SETTINGS_PATH", cls.settings_path),
            patch.object(server, "AUTOSTART_PATH", cls.autostart_path),
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
        self.assertEqual(self.request(), (200, {"autoStart": True, "kiosk": False, "autostartInstalled": False}))

    def test_device_file_overrides_config_defaults(self):
        self.config_path.write_text(json.dumps({"startup": {"autoStart": True, "kiosk": False}}), encoding="utf-8")
        self.settings_path.write_text(json.dumps({"autoStart": False, "kiosk": True}), encoding="utf-8")
        self.assertEqual(self.request(), (200, {"autoStart": False, "kiosk": True, "autostartInstalled": False}))

    def test_settings_ui_post_persists_local_override(self):
        self.config_path.write_text(json.dumps({"startup": {"autoStart": False, "kiosk": True}}), encoding="utf-8")
        payload = json.dumps({"autoStart": True, "kiosk": False}).encode("utf-8")
        self.assertEqual(self.request(payload), (200, {"autoStart": True, "kiosk": False, "autostartInstalled": False}))
        self.assertEqual(json.loads(self.settings_path.read_text(encoding="utf-8")), {"autoStart": True, "kiosk": False})

    def test_invalid_config_falls_back_to_safe_startup_defaults(self):
        self.config_path.write_text("not-json", encoding="utf-8")
        self.assertEqual(self.request(), (200, {"autoStart": False, "kiosk": True, "autostartInstalled": False}))

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
