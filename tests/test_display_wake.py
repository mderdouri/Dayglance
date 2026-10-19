"""Tests for safe display wake and idle-timer reset adapters."""

import json
import os
import sys
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server  # noqa: E402


class DisplayWakeTests(unittest.TestCase):
    @patch("server.shutil.which", side_effect=lambda name: f"/usr/bin/{name}")
    @patch("server.subprocess.run")
    @patch.dict("server.os.environ", {"WAYLAND_DISPLAY": "wayland-test", "XDG_RUNTIME_DIR": "/run/user/1000"}, clear=False)
    def test_wayland_wakes_outputs_and_restarts_the_swayidle_service(self, run, _which):
        def result(args, **_kwargs):
            command = " ".join([os.path.basename(args[0]), *args[1:]])
            stdout = {
                "wlopm --json": json.dumps([{"output": "DSI-TEST", "power-mode": "off"}]),
                'systemctl --user show --property=Id,ActiveState,SubState,ExecStart --all --no-pager *.service': "Id=example-idle.service\nActiveState=active\nSubState=running\nExecStart={ path=/usr/bin/swayidle ; argv[]=/usr/bin/swayidle -w ; }\n",
            }.get(command, "")
            return CompletedProcess(args, 0, stdout, "")
        run.side_effect = result
        with patch.object(server.sys, "platform", "linux"):
            success, message = server.wake_display()
        self.assertTrue(success, f"{message}; calls={[item.args[0] for item in run.call_args_list]!r}")
        self.assertIn("idle timer restarted", message)
        self.assertEqual(run.call_args_list[0].args[0], ["/usr/bin/wlopm", "--json"])
        self.assertEqual(run.call_args_list[1].args[0], ["/usr/bin/wlopm", "--on", "DSI-TEST"])
        self.assertEqual(run.call_args_list[-1].args[0], ["/usr/bin/systemctl", "--user", "restart", "example-idle.service"])

    @patch("server.shutil.which", side_effect=lambda name: f"/usr/bin/{name}")
    @patch("server.subprocess.run")
    @patch.dict("server.os.environ", {"DISPLAY": ":0", "WAYLAND_DISPLAY": ""}, clear=False)
    def test_x11_wakes_display_and_resets_screensaver_timer(self, run, _which):
        with patch.object(server.sys, "platform", "linux"):
            success, message = server.wake_display()
        self.assertTrue(success)
        self.assertIn("idle timer restarted", message)
        self.assertEqual([item.args[0] for item in run.call_args_list], [
            ["/usr/bin/xset", "dpms", "force", "on"],
            ["/usr/bin/xset", "s", "reset"],
        ])

    @patch("server.shutil.which", return_value=None)
    @patch("server.subprocess.run")
    @patch.dict("server.os.environ", {}, clear=True)
    def test_unsupported_session_fails_without_running_commands(self, run, _which):
        with patch.object(server.sys, "platform", "linux"):
            success, message = server.wake_display()
        self.assertFalse(success)
        self.assertIn("No supported", message)
        run.assert_not_called()

    @patch("server.shutil.which", side_effect=lambda name: f"/usr/bin/{name}")
    @patch("server.subprocess.run")
    @patch.dict("server.os.environ", {"WAYLAND_DISPLAY": "wayland-test", "XDG_RUNTIME_DIR": "/run/user/1000"}, clear=False)
    def test_wayland_requires_an_idle_manager_for_a_timer_reset(self, run, _which):
        def result(args, **_kwargs):
            stdout = json.dumps([{"output": "DSI-TEST", "power-mode": "on"}]) if args[-1] == "--json" else ""
            if "--property=Id,ActiveState,SubState,ExecStart" in args:
                stdout = "Id=unrelated.service\nActiveState=active\nSubState=running\nExecStart={ path=/usr/bin/unrelated ; argv[]=/usr/bin/unrelated ; }\n"
            return CompletedProcess(args, 0, stdout, "")
        run.side_effect = result
        with patch.object(server.sys, "platform", "linux"):
            success, message = server.wake_display()
        self.assertFalse(success)
        self.assertIn("no running swayidle", message)
        self.assertTrue(any(item.args[0][:3] == ["/usr/bin/wlopm", "--on", "DSI-TEST"] for item in run.call_args_list))

    @patch("server.shutil.which", side_effect=lambda name: f"/usr/bin/{name}")
    @patch("server.subprocess.run")
    @patch.dict("server.os.environ", {"WAYLAND_DISPLAY": "wayland-test", "XDG_RUNTIME_DIR": "/run/user/1000"}, clear=False)
    def test_wayland_does_not_restart_an_inactive_swayidle_service(self, run, _which):
        def result(args, **_kwargs):
            stdout = json.dumps([{"output": "DSI-TEST", "power-mode": "on"}]) if args[-1] == "--json" else ""
            if "--property=Id,ActiveState,SubState,ExecStart" in args:
                stdout = "Id=example-idle.service\nActiveState=inactive\nSubState=dead\nExecStart={ path=/usr/bin/swayidle ; argv[]=/usr/bin/swayidle -w ; }\n"
            return CompletedProcess(args, 0, stdout, "")
        run.side_effect = result
        with patch.object(server.sys, "platform", "linux"):
            success, message = server.wake_display()
        self.assertFalse(success)
        self.assertIn("no running swayidle", message)
        self.assertFalse(any("restart" in item.args[0] for item in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
