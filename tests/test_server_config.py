"""Integration tests for device startup settings and config.json precedence."""

import io
import json
import os
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
        cls.station_settings_path = root / "device-station-settings.json"
        cls.station_credentials_path = root / "device-station-credentials.json"
        cls.autostart_path = root / "autostart" / "dayglance.desktop"
        cls.labwc_autostart_path = cls.home / ".config" / "labwc" / "autostart"
        cls.patches = [
            patch.object(server, "CONFIG_PATH", cls.config_path),
            patch.object(server, "DEVICE_SETTINGS_PATH", cls.settings_path),
            patch.object(server, "RADAR_CREDENTIALS_PATH", cls.radar_key_path),
            patch.object(server, "RADAR_USAGE_PATH", cls.radar_usage_path),
            patch.object(server, "STATION_SETTINGS_PATH", cls.station_settings_path),
            patch.object(server, "STATION_CREDENTIALS_PATH", cls.station_credentials_path),
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
        self.station_settings_path.unlink(missing_ok=True)
        self.station_credentials_path.unlink(missing_ok=True)
        server._station_config = {"receiver": {}, "integrations": []}
        server._station_observations.clear()
        server._station_source_status.clear()
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
        self.assertIn("Provider key profiles", settings)
        self.assertIn("Add or edit a cloud station", settings)
        self.assertIn('type="password"', settings)
        self.assertIn("Local uploads are still configured through", settings)
        self.assertIn("Cloud changes apply live", settings)
        self.assertIn("From config.json", settings)

    def test_station_manager_accepts_multiple_cities_and_stores_device_settings(self):
        sources = []
        for index in range(1, 11):
            if index <= 5:
                sources.append({"id": f"ambient-{index}", "name": f"Station {index}", "provider": "ambient-weather",
                                "connection": "cloud-api", "deviceId": f"00:11:22:33:44:{index:02d}",
                                "credentialsId": "Home account", "locationId": f"city-{index}", "staleAfterSeconds": 600})
            else:
                sources.append({"id": f"pws-{index}", "name": f"Station {index}", "provider": "weather-underground",
                                "connection": "cloud-api", "stationId": f"KDCWASH{index:04d}",
                                "credentialsId": "Weather Company", "locationId": f"city-{index}", "staleAfterSeconds": 600})
        status, data = self.request(json.dumps({"integrations": sources}).encode(), path="api/station-settings")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["integrations"]), 10)
        self.assertTrue(all(source["managed"] for source in data["integrations"]))
        self.assertEqual(len(json.loads(self.station_settings_path.read_text())["integrations"]), 10)
        self.assertTrue(all(source["connection"] == "cloud-api" for source in server._station_config["integrations"]))

    def test_station_manager_settings_are_loaded_again_after_restart(self):
        source = {"id": "cloud-home", "name": "Home station", "provider": "weather-underground",
                  "connection": "cloud-api", "stationId": "KDC123", "credentialsId": "PWS account",
                  "locationId": "home", "staleAfterSeconds": 600}
        status, _ = self.request(json.dumps({"integrations": [source]}).encode(), path="api/station-settings")
        self.assertEqual(status, 200)
        reloaded = server.load_station_configuration()
        self.assertEqual(len(reloaded["integrations"]), 1)
        self.assertEqual(reloaded["integrations"][0]["id"], "cloud-home")
        self.assertTrue(reloaded["integrations"][0]["managed"])

    def test_config_defined_station_cannot_become_device_managed(self):
        config_source = {"id": "config-home", "name": "Configured station", "provider": "weather-underground",
                         "connection": "cloud-api", "enabled": True, "stationId": "KDC123",
                         "credentialsId": "PWS account", "locationId": "home", "managed": True}
        self.config_path.write_text(json.dumps({"stationIntegrations": [config_source]}), encoding="utf-8")
        loaded = server.load_station_configuration(managed_override=[])
        self.assertEqual(len(loaded["integrations"]), 1)
        self.assertFalse(loaded["integrations"][0]["managed"])

    def test_station_key_profiles_are_saved_privately_and_never_returned(self):
        secret = "test-ambient-api-key-123456"
        payload = {"provider": "ambient-weather", "id": "Home", "apiKey": secret, "applicationKey": "test-app-key-123456"}
        status, data = self.request(json.dumps(payload).encode(), path="api/station-credentials")
        self.assertEqual(status, 200)
        self.assertNotIn(secret, json.dumps(data))
        self.assertEqual(json.loads(self.station_credentials_path.read_text())["ambientWeatherAccounts"]["Home"]["apiKey"], secret)
        status, metadata = self.request(path="api/station-settings")
        self.assertEqual(status, 200)
        self.assertIn({"provider": "ambient-weather", "id": "Home", "configured": True}, metadata["profiles"])
        self.assertNotIn(secret, json.dumps(metadata))
        if os.name == "posix":
            self.assertEqual(self.station_credentials_path.stat().st_mode & 0o777, 0o600)

    def test_station_manager_rejects_duplicate_city_and_local_upload(self):
        sources = [
            {"id": "one", "provider": "weather-underground", "connection": "cloud-api", "stationId": "KDC123", "credentialsId": "wu", "locationId": "same-city"},
            {"id": "two", "provider": "weather-underground", "connection": "cloud-api", "stationId": "KDC124", "credentialsId": "wu", "locationId": "same-city"},
        ]
        status, _ = self.request(json.dumps({"integrations": sources}).encode(), path="api/station-settings")
        self.assertEqual(status, 400)
        self.assertFalse(self.station_settings_path.exists())
        status, _ = self.request(json.dumps({"integrations": [{"id": "local", "provider": "ambient-weather", "connection": "local-upload"}]}).encode(), path="api/station-settings")
        self.assertEqual(status, 400)

    def test_station_manager_rejects_remote_writes(self):
        payload = json.dumps({"integrations": []}).encode()
        with patch.object(server.Handler, "is_local_app_request", return_value=False):
            status, _ = self.request(payload, path="api/station-settings")
        self.assertEqual(status, 403)
        self.assertFalse(self.station_settings_path.exists())

    def test_station_profile_deletion_is_blocked_while_a_station_uses_it(self):
        profile = {"provider": "weather-underground", "id": "PWS account", "apiKey": "weather-company-key-1234"}
        status, _ = self.request(json.dumps(profile).encode(), path="api/station-credentials")
        self.assertEqual(status, 200)
        station = {"id": "pws", "name": "PWS", "provider": "weather-underground", "connection": "cloud-api", "stationId": "KDC123", "credentialsId": "PWS account", "locationId": "home"}
        status, _ = self.request(json.dumps({"integrations": [station]}).encode(), path="api/station-settings")
        self.assertEqual(status, 200)
        status, data = self.request(path="api/station-credentials/weather-underground/PWS%20account", method="DELETE")
        self.assertEqual(status, 409)
        self.assertIn("Remove or reassign", data["error"])
        status, _ = self.request(json.dumps({"integrations": []}).encode(), path="api/station-settings")
        self.assertEqual(status, 200)
        status, data = self.request(path="api/station-credentials/weather-underground/PWS%20account", method="DELETE")
        self.assertEqual(status, 200)
        self.assertEqual(data["profiles"], [])

    def test_local_station_status_matches_freshness_of_received_sample(self):
        server._station_config = {"receiver": {}, "integrations": [{"id": "local", "name": "Local station",
                                "locationId": "home", "provider": "ambient-weather", "connection": "local-upload",
                                "staleAfterSeconds": 600}]}
        server._station_observations["local"] = {"observedAt": 100, "receivedAt": 100}
        fresh = {"available": True, "fresh": True, "ageSeconds": 5, "observation": {"tempf": 70}}
        with patch.object(server, "station_freshness", return_value=fresh):
            payload = server.station_status_payload()
        self.assertEqual(payload["integrations"][0]["status"], "Receiving local uploads")
        stale = {"available": True, "fresh": False, "ageSeconds": 700, "observation": {"tempf": 70}}
        with patch.object(server, "station_freshness", return_value=stale):
            payload = server.station_status_payload()
        self.assertEqual(payload["integrations"][0]["status"], "Last local reading is stale")

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
