
"""Unit tests for the APK-Xray dynamic subprocess controller.

These tests mock host subprocesses. They do not start ADB, Docker,
an emulator, or execute an APK.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.dynamic.subprocess_controller import (
    ProductionSandboxController,
    SandboxControllerError,
)


class DynamicControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.controller = ProductionSandboxController(
            adb_target="127.0.0.1:5555",
            artifact_root=self.temp_dir.name,
            command_timeout_seconds=5,
            run_timeout_seconds=30,
        )

    @patch("backend.dynamic.subprocess_controller.subprocess.run")
    def test_command_uses_argument_list_without_shell(
        self, mock_run: Mock
    ) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="device",
            stderr="",
        )

        result = self.controller._run_command(["get-state"])

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "device")

        args, kwargs = mock_run.call_args
        self.assertEqual(
            args[0],
            ["adb", "-s", "127.0.0.1:5555", "get-state"],
        )
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 5)
        self.assertTrue(kwargs["capture_output"])

    @patch("backend.dynamic.subprocess_controller.subprocess.run")
    def test_nonzero_exit_raises_sanitized_error(
        self, mock_run: Mock
    ) -> None:
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="sensitive device diagnostic",
        )

        with self.assertRaises(SandboxControllerError) as context:
            self.controller._run_command(["get-state"])

        self.assertIn("get-state", str(context.exception))
        self.assertNotIn(
            "sensitive device diagnostic", str(context.exception)
        )

    @patch("backend.dynamic.subprocess_controller.subprocess.run")
    def test_command_timeout_raises_controller_error(
        self, mock_run: Mock
    ) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["adb", "get-state"],
            timeout=5,
        )

        with self.assertRaisesRegex(
            SandboxControllerError, "timed out"
        ):
            self.controller._run_command(["get-state"])

    @patch("backend.dynamic.subprocess_controller.subprocess.run")
    def test_missing_adb_executable_is_handled(
        self, mock_run: Mock
    ) -> None:
        mock_run.side_effect = FileNotFoundError("adb not found")

        with self.assertRaisesRegex(
            SandboxControllerError, "Unable to start"
        ):
            self.controller._run_command(["get-state"])

    def test_invalid_package_is_rejected_before_health_check(self) -> None:
        with patch.object(
            self.controller, "verify_environment_health"
        ) as health:
            result = self.controller.execute_dynamic_analysis(
                "missing.apk",
                "invalid;package",
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"], "Invalid Android package name.")
        health.assert_not_called()

    def test_missing_apk_is_rejected_before_health_check(self) -> None:
        missing_apk = Path(self.temp_dir.name) / "missing.apk"

        with patch.object(
            self.controller, "verify_environment_health"
        ) as health:
            result = self.controller.execute_dynamic_analysis(
                missing_apk,
                "org.example.app",
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("staged APK", result["error"])
        health.assert_not_called()

    def test_empty_apk_is_rejected(self) -> None:
        empty_apk = Path(self.temp_dir.name) / "empty.apk"
        empty_apk.touch()

        with patch.object(
            self.controller, "verify_environment_health"
        ) as health:
            result = self.controller.execute_dynamic_analysis(
                empty_apk,
                "org.example.app",
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"], "The staged APK is empty.")
        health.assert_not_called()

    def test_unhealthy_emulator_prevents_job_creation(self) -> None:
        apk = Path(self.temp_dir.name) / "sample.apk"
        apk.write_bytes(b"mock APK bytes")

        with patch.object(
            self.controller, "verify_environment_health", return_value=False
        ), patch.object(self.controller, "_run_command") as run_command:
            result = self.controller.execute_dynamic_analysis(
                apk,
                "org.example.app",
            )

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("emulator is unavailable", result["error"])
        run_command.assert_not_called()
        self.assertEqual(
            list(Path(self.temp_dir.name).iterdir()),
            [apk],
        )

    def test_invalid_adb_target_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductionSandboxController(
                adb_target="127.0.0.1;whoami"
            )

    def test_out_of_range_adb_port_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ProductionSandboxController(
                adb_target="127.0.0.1:70000"
            )

    def test_timeout_configuration_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            ProductionSandboxController(
                command_timeout_seconds=301
            )

        with self.assertRaises(ValueError):
            ProductionSandboxController(
                run_timeout_seconds=901
            )


if __name__ == "__main__":
    unittest.main()
