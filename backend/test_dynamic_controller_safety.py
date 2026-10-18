
"""Regression tests for dynamic controller safety behavior.

These tests mock subprocesses and never start ADB or an emulator.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.dynamic.subprocess_controller import (
    ProductionSandboxController,
    SandboxControllerError,
)


class DynamicControllerSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.controller = ProductionSandboxController(
            adb_target="127.0.0.1:5555",
            artifact_root=self.temp_dir.name,
            command_timeout_seconds=5,
            run_timeout_seconds=30,
            max_log_bytes=1024,
        )

    @patch("backend.dynamic.subprocess_controller.subprocess.run")
    def test_command_timeout_never_exceeds_configured_limit(
        self, mock_run: Mock
    ) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="device",
            stderr="",
        )

        self.controller._run_command(["get-state"], timeout=100)

        self.assertEqual(mock_run.call_args.kwargs["timeout"], 5)

    def test_remaining_time_raises_when_budget_is_exhausted(self) -> None:
        with patch(
            "backend.dynamic.subprocess_controller.time.monotonic",
            return_value=200.0,
        ):
            with self.assertRaisesRegex(
                SandboxControllerError, "time budget exceeded"
            ):
                self.controller._remaining_time(started=100.0)

    def test_invalid_package_does_not_touch_emulator(self) -> None:
        with patch.object(
            self.controller, "verify_environment_health"
        ) as health:
            result = self.controller.execute_dynamic_analysis(
                "not-needed.apk",
                "bad;package",
            )

        self.assertEqual(result["status"], "FAILED")
        health.assert_not_called()

    def test_empty_apk_does_not_touch_emulator(self) -> None:
        apk = Path(self.temp_dir.name) / "empty.apk"
        apk.touch()

        with patch.object(
            self.controller, "verify_environment_health"
        ) as health:
            result = self.controller.execute_dynamic_analysis(
                apk,
                "org.example.app",
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"], "The staged APK is empty.")
        health.assert_not_called()

    @patch("backend.dynamic.subprocess_controller.subprocess.run")
    def test_nonzero_adb_exit_does_not_return_output(
        self, mock_run: Mock
    ) -> None:
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="private device detail",
        )

        with self.assertRaises(SandboxControllerError) as context:
            self.controller._run_command(["install", "sample.apk"])

        self.assertNotIn("private device detail", str(context.exception))

    def test_invalid_log_limit_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductionSandboxController(max_log_bytes=100)

    def test_invalid_command_timeout_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductionSandboxController(command_timeout_seconds=0)

    def test_invalid_run_timeout_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductionSandboxController(run_timeout_seconds=901)

    def test_logcat_cleanup_timeout_is_detected(self) -> None:
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="adb logcat", timeout=5),
            subprocess.TimeoutExpired(cmd="adb logcat", timeout=5),
        ]

        collector = Mock()
        collector.is_alive.return_value = False

        with self.assertRaises(SandboxControllerError):
            self.controller._stop_logcat(process, collector)

        process.kill.assert_called_once()

    def test_logcat_cleanup_joins_collector(self) -> None:
        process = Mock()
        process.poll.return_value = 0
        process.wait.return_value = 0

        collector = Mock()
        collector.is_alive.return_value = False

        self.controller._stop_logcat(process, collector)

        collector.join.assert_called_once_with(timeout=5)


if __name__ == "__main__":
    unittest.main()
