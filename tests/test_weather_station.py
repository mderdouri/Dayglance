"""Tests for local personal-weather-station uploads and configuration."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
import server  # noqa: E402
from weather_station import freshness, normalize_upload, normalize_weather_company_pws  # noqa: E402


class StationUploadTests(unittest.TestCase):
    def test_upload_keeps_known_plausible_fields_only(self):
        sample = normalize_upload({"tempf": "71.5", "humidity": "48", "password": "ignored", "rainin": "-1"}, received_at=1_800_000_000)
        self.assertEqual(sample["tempf"], 71.5)
        self.assertEqual(sample["humidity"], 48)
        self.assertNotIn("password", sample)
        self.assertNotIn("rainin", sample)
        self.assertEqual(sample["observedAt"], 1_800_000_000)

    def test_upload_rejects_when_no_usable_outdoor_values_remain(self):
        with self.assertRaisesRegex(ValueError, "no usable outdoor"):
            normalize_upload({"tempf": "999", "password": "value"}, received_at=1_800_000_000)

    def test_ambient_weather_protocol_field_names_are_normalized(self):
        sample = normalize_upload({"tempf": "70", "baromrelin": "29.9", "tempinf": "72", "humidityin": "40", "hourlyrainin": "0.02", "MAC": "00:00:00:00:00:00"}, received_at=1_800_000_000)
        self.assertEqual(sample["baromin"], 29.9)
        self.assertEqual(sample["indoortempf"], 72)
        self.assertEqual(sample["indoorhumidity"], 40)
        self.assertEqual(sample["rainin"], 0.02)
        self.assertNotIn("mac", sample)

    def test_upload_rejects_malformed_and_out_of_window_timestamps(self):
        for value in ("not-a-date", "2020-01-01 00:00:00", "2030-01-01 00:00:00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_upload({"tempf": "70", "dateutc": value}, received_at=1_800_000_000)

    def test_freshness_uses_observation_time_and_ages_out(self):
        sample = {"receivedAt": 1_800_000_000, "observedAt": 1_799_999_900}
        fresh = freshness(sample, 300, now=1_800_000_000)
        stale = freshness(sample, 300, now=1_800_000_400)
        self.assertTrue(fresh["fresh"])
        self.assertEqual(fresh["ageSeconds"], 100)
        self.assertFalse(stale["fresh"])

    def test_weather_company_pws_fields_are_converted_to_normalized_units(self):
        sample = normalize_weather_company_pws({
            "epoch": 1_800_000_000, "humidity": 48, "winddir": 270, "uv": 3,
            "imperial": {"temp": 70.5, "windSpeed": 4.2, "windGust": 7.1, "precipRate": 0.01,
                         "precipTotal": 0.2, "pressure": 29.9, "dewpt": 50.1},
        }, received_at=1_800_000_000)
        self.assertEqual(sample["tempf"], 70.5)
        self.assertEqual(sample["windspeedmph"], 4.2)
        self.assertEqual(sample["baromin"], 29.9)
        self.assertEqual(sample["rainin"], 0.01)
        self.assertEqual(sample["observedAt"], 1_800_000_000)


class StationConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dayglance-station-config-")
        self.config_path = Path(self.temp.name) / "config.json"
        self.config_patch = patch.object(server, "CONFIG_PATH", self.config_path)
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        self.temp.cleanup()

    def write_config(self, **overrides):
        config = {
            "stationReceiver": {"bindAddress": "192.168.1.50", "port": 8082, "path": "/weatherstation/updateweatherstation.php"},
            "stationIntegrations": [{
                "id": "backyard", "name": "Backyard station", "provider": "ambient-weather",
                "connection": "local-upload", "enabled": True, "sourceIp": "192.168.1.60",
                "locationId": "home", "staleAfterSeconds": 600,
            }],
        }
        config.update(overrides)
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def test_valid_local_station_config_loads_without_credentials(self):
        self.write_config()
        result = server.load_station_configuration()
        self.assertEqual(result["integrations"][0]["sourceIp"], "192.168.1.60")
        self.assertEqual(result["integrations"][0]["locationId"], "home")
        self.assertNotIn("password", json.dumps(result).lower())

    def test_disabled_station_does_not_enable_or_bind_receiver(self):
        self.write_config(stationIntegrations=[{"id": "backyard", "enabled": False}])
        self.assertEqual(server.load_station_configuration()["integrations"], [])

    def test_rejects_non_private_sources_and_public_listeners(self):
        self.write_config(stationIntegrations=[{"id": "backyard", "name": "Station", "provider": "ambient-weather", "connection": "local-upload", "enabled": True, "sourceIp": "8.8.8.8", "locationId": None}])
        with self.assertRaisesRegex(ValueError, "private IPv4"):
            server.load_station_configuration()
        self.write_config(stationReceiver={"bindAddress": "0.0.0.0", "port": 8082, "path": "/upload"})
        with self.assertRaisesRegex(ValueError, "specific private IPv4"):
            server.load_station_configuration()

    def test_enforces_one_station_per_configured_city(self):
        self.write_config(stationIntegrations=[
            {"id": "one", "provider": "ambient-weather", "connection": "local-upload", "enabled": True, "sourceIp": "192.168.1.60", "locationId": "home"},
            {"id": "two", "provider": "ambient-weather", "connection": "local-upload", "enabled": True, "sourceIp": "192.168.1.88", "locationId": "home"},
        ])
        with self.assertRaisesRegex(ValueError, "Only one enabled"):
            server.load_station_configuration()

    def test_valid_ambient_cloud_station_does_not_need_receiver_address_or_secret_in_config(self):
        self.write_config(
            stationReceiver={"bindAddress": "127.0.0.1", "port": 8082, "path": "/upload"},
            stationIntegrations=[{
                "id": "cloud-backyard", "name": "Cloud Backyard", "provider": "ambient-weather",
                "connection": "cloud-api", "enabled": True, "deviceId": "00:11:22:33:44:55",
                "credentialsId": "home-account", "locationId": "home", "staleAfterSeconds": 600,
            }],
        )
        result = server.load_station_configuration()
        self.assertEqual(result["integrations"][0]["connection"], "cloud-api")
        self.assertEqual(result["integrations"][0]["deviceId"], "00:11:22:33:44:55")
        self.assertNotIn("apiKey", json.dumps(result))

    def test_cloud_station_requires_valid_ambient_mac(self):
        self.write_config(stationIntegrations=[{
            "id": "cloud", "provider": "ambient-weather", "connection": "cloud-api",
            "enabled": True, "deviceId": "not-a-mac", "locationId": None,
        }])
        with self.assertRaisesRegex(ValueError, "12-digit hexadecimal"):
            server.load_station_configuration()

    def test_valid_weather_underground_cloud_station_uses_station_id(self):
        self.write_config(stationIntegrations=[{
            "id": "wu", "name": "WU station", "provider": "weather-underground",
            "connection": "cloud-api", "enabled": True, "stationId": "KDCWASHINGTON123",
            "credentialsId": "weather-company", "locationId": "home", "staleAfterSeconds": 600,
        }])
        result = server.load_station_configuration()
        self.assertEqual(result["integrations"][0]["stationId"], "KDCWASHINGTON123")
        self.assertEqual(result["integrations"][0]["provider"], "weather-underground")

    def test_weather_underground_station_id_rejects_path_separators(self):
        self.write_config(stationIntegrations=[{
            "id": "wu", "provider": "weather-underground", "connection": "cloud-api",
            "enabled": True, "stationId": "../outside", "locationId": None,
        }])
        with self.assertRaisesRegex(ValueError, "valid stationId"):
            server.load_station_configuration()

    def test_status_payload_never_exposes_station_source_ip(self):
        config = {"integrations": [{"id": "backyard", "name": "Backyard", "locationId": None, "provider": "ambient-weather", "connection": "local-upload", "staleAfterSeconds": 600, "sourceIp": "192.168.1.60"}]}
        observation = {"tempf": 70.0, "observedAt": time.time(), "receivedAt": time.time()}
        with patch.object(server, "_station_config", config), patch.object(server, "_station_observations", {"backyard": observation}):
            payload = json.dumps(server.station_status_payload())
        self.assertIn("Backyard", payload)
        self.assertIn("tempf", payload)
        self.assertNotIn("192.168.1.60", payload)

    def test_cloud_poll_groups_same_account_and_keeps_credentials_out_of_status(self):
        now_ms = int(time.time() * 1000)
        devices = [
            {"macAddress": "00:11:22:33:44:55", "lastData": {"tempf": 72.3, "humidity": 44, "dateutc": now_ms}},
            {"macAddress": "00:11:22:33:44:66", "lastData": {"tempf": 65.1, "humidity": 51, "dateutc": now_ms}},
        ]

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _limit):
                return json.dumps(devices).encode("utf-8")

        config = {"integrations": [
            {"id": "one", "name": "One", "locationId": None, "provider": "ambient-weather", "connection": "cloud-api", "staleAfterSeconds": 600, "deviceId": "00:11:22:33:44:55", "credentialsId": "account"},
            {"id": "two", "name": "Two", "locationId": None, "provider": "ambient-weather", "connection": "cloud-api", "staleAfterSeconds": 600, "deviceId": "00:11:22:33:44:66", "credentialsId": "account"},
        ]}
        with patch.object(server, "_station_config", config), \
             patch.object(server, "_station_observations", {}), \
             patch.object(server, "_station_source_status", {}), \
             patch.object(server, "STATION_CREDENTIALS_PATH", self.config_path), \
             patch.object(server, "urlopen", return_value=Response()) as mock_urlopen:
            self.config_path.write_text(json.dumps({"ambientWeatherAccounts": {"account": {"apiKey": "private-api-key", "applicationKey": "private-app-key"}}}), encoding="utf-8")
            server.refresh_ambient_weather_cloud_once()
            self.assertEqual(mock_urlopen.call_count, 1)
            payload = json.dumps(server.station_status_payload())
        self.assertIn("72.3", payload)
        self.assertIn("65.1", payload)
        self.assertIn("Connected to Ambient Weather", payload)
        self.assertNotIn("private-api-key", payload)
        self.assertNotIn("private-app-key", payload)

    def test_weather_company_poll_normalizes_data_and_never_returns_api_key(self):
        response_payload = {"observations": [{
            "stationID": "KDCWASHINGTON123", "epoch": int(time.time()), "humidity": 50,
            "winddir": 180, "uv": 1,
            "imperial": {"temp": 69, "windSpeed": 2, "windGust": 3, "pressure": 30.1,
                         "precipRate": 0, "precipTotal": 0, "dewpt": 48},
        }]}

        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False
            def read(self, _limit):
                return json.dumps(response_payload).encode("utf-8")

        config = {"integrations": [{
            "id": "wu", "name": "WU station", "locationId": None, "provider": "weather-underground",
            "connection": "cloud-api", "staleAfterSeconds": 600, "stationId": "KDCWASHINGTON123",
            "credentialsId": "account",
        }]}
        with patch.object(server, "_station_config", config), \
             patch.object(server, "_station_observations", {}), \
             patch.object(server, "_station_source_status", {}), \
             patch.object(server, "STATION_CREDENTIALS_PATH", self.config_path), \
             patch.object(server, "urlopen", return_value=Response()) as mock_urlopen:
            self.config_path.write_text(json.dumps({"weatherUndergroundAccounts": {"account": {"apiKey": "private-weather-key"}}}), encoding="utf-8")
            server.refresh_weather_underground_cloud_once()
            self.assertEqual(mock_urlopen.call_count, 1)
            payload = json.dumps(server.station_status_payload())
        self.assertIn("69", payload)
        self.assertIn("Connected to Weather Underground", payload)
        self.assertNotIn("private-weather-key", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
