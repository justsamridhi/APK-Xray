
"""Bounded ADB controller for APK-Xray dynamic analysis.

Requires a dedicated worker and a disposable, externally isolated emulator.
This module does not create Docker isolation or restore emulator snapshots.
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

logger = logging.getLogger("APK_Xray.DynamicController")

PACKAGE_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$"
)


@dataclass(frozen=True)
class CommandResult:
    """Result of a bounded ADB command."""

    returncode: int
    stdout: str
    stderr: str


class SandboxControllerError(RuntimeError):
    """A safe-to-report controller failure."""


class ProductionSandboxController:
    """Control a pre-provisioned Android emulator through ADB."""

    def __init__(
        self,
        *,
        adb_target: str = "127.0.0.1:5555",
        adb_executable: str = "adb",
        artifact_root: str | Path = "data/dynamic",
        command_timeout_seconds: int = 30,
        run_timeout_seconds: int = 180,
        max_log_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+:\d{1,5}", adb_target):
            raise ValueError("Invalid ADB target format.")

        port = int(adb_target.rsplit(":", 1)[1])
        if not 1 <= port <= 65535:
            raise ValueError("ADB port is out of range.")

        if not 1 <= command_timeout_seconds <= 300:
            raise ValueError(
                "Command timeout must be between 1 and 300 seconds."
            )

        if not 1 <= run_timeout_seconds <= 900:
            raise ValueError(
                "Run timeout must be between 1 and 900 seconds."
            )

        if max_log_bytes < 1024:
            raise ValueError("Log limit must be at least 1024 bytes.")

        if (
            not isinstance(adb_executable, str)
            or not adb_executable.strip()
            or "\x00" in adb_executable
        ):
            raise ValueError("Invalid ADB executable.")

        self.adb_target = adb_target
        self.adb_executable = adb_executable
        self.artifact_root = Path(artifact_root).resolve()
        self.command_timeout = command_timeout_seconds
        self.run_timeout = run_timeout_seconds
        self.max_log_bytes = max_log_bytes

    def _run_command(
        self,
        args: Sequence[str],
        *,
        timeout: int | None = None,
    ) -> CommandResult:
        """Run ADB without a shell, enforcing the command timeout."""
        if not args or any(
            not isinstance(arg, str) or "\x00" in arg for arg in args
        ):
            raise ValueError("Command arguments must be valid strings.")

        requested_timeout = (
            self.command_timeout if timeout is None else timeout
        )
        if requested_timeout <= 0:
            raise ValueError("Command timeout must be positive.")

        effective_timeout = min(
            requested_timeout,
            self.command_timeout,
        )

        command = [
            self.adb_executable,
            "-s",
            self.adb_target,
            *args,
        ]

        # Do not log untrusted arguments, APK paths, or command output.
        logger.info("Running ADB operation: %s", args[0])

        try:
            result = subprocess.run(
                command,
                shell=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=effective_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxControllerError(
                f"ADB operation timed out: {args[0]}"
            ) from exc
        except OSError as exc:
            raise SandboxControllerError(
                "Unable to start the ADB executable."
            ) from exc

        if result.returncode != 0:
            logger.warning(
                "ADB operation failed: operation=%s exit_code=%d",
                args[0],
                result.returncode,
            )
            raise SandboxControllerError(
                f"ADB operation failed: {args[0]} "
                f"(exit code {result.returncode})."
            )

        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def verify_environment_health(self) -> bool:
        """Check ADB connectivity only, not cleanliness or isolation."""
        try:
            connect = subprocess.run(
                [
                    self.adb_executable,
                    "connect",
                    self.adb_target,
                ],
                shell=False,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=min(5, self.command_timeout),
                check=False,
            )

            if connect.returncode != 0:
                return False

            state = self._run_command(
                ["get-state"],
                timeout=min(5, self.command_timeout),
            )
            return state.stdout.strip() == "device"

        except (SandboxControllerError, OSError, subprocess.TimeoutExpired):
            return False

    def _remaining_time(self, started: float) -> float:
        """Return remaining run budget or raise when it is exhausted."""
        remaining = self.run_timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise SandboxControllerError(
                "Dynamic-analysis time budget exceeded."
            )
        return remaining

    def _stop_logcat(
        self,
        process: subprocess.Popen[bytes],
        collector: threading.Thread,
    ) -> None:
        """Stop and reap logcat; report cleanup failures."""
        try:
            if process.poll() is None:
                process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

            collector.join(timeout=5)
            if collector.is_alive():
                raise SandboxControllerError(
                    "Log collector did not stop."
                )

        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxControllerError(
                "Unable to stop the logcat process safely."
            ) from exc

    def execute_dynamic_analysis(
        self,
        local_apk_path: str | Path,
        package_name: str,
    ) -> dict[str, str]:
        """Collect bounded logcat while briefly exercising an installed APK.

        A SUCCESS result describes collection and cleanup, not APK safety.
        The caller must supply a trusted, worker-controlled staging path.
        """
        if not isinstance(package_name, str) or not PACKAGE_RE.fullmatch(
            package_name
        ):
            return {
                "status": "FAILED",
                "error": "Invalid Android package name.",
            }

        try:
            apk_path = Path(local_apk_path).resolve(strict=True)

            if not apk_path.is_file() or apk_path.suffix.lower() != ".apk":
                return {
                    "status": "FAILED",
                    "error": "A staged APK file is required.",
                }

            if apk_path.stat().st_size <= 0:
                return {
                    "status": "FAILED",
                    "error": "The staged APK is empty.",
                }

        except (OSError, ValueError, RuntimeError):
            return {
                "status": "FAILED",
                "error": "Unable to access the staged APK.",
            }

        if not self.verify_environment_health():
            return {
                "status": "FAILED",
                "error": "The configured emulator is unavailable.",
            }

        job_id = uuid.uuid4().hex
        started = time.monotonic()
        job_dir: Path | None = None
        log_path: Path | None = None
        log_proc: subprocess.Popen[bytes] | None = None
        collector: threading.Thread | None = None
        log_file = None
        log_stream = None
        installed = False
        install_attempted = False
        log_limit_hit = threading.Event()
        collector_errors: list[BaseException] = []
        failure_message: str | None = None
        cleanup_failed = False
        success_result: dict[str, str] | None = None

        try:
            self.artifact_root.mkdir(parents=True, exist_ok=True)
            job_dir = self.artifact_root / job_id
            job_dir.mkdir(exist_ok=False)
            log_path = job_dir / "logcat.txt"

            self._remaining_time(started)
            self._run_command(["logcat", "-c"])

            self._remaining_time(started)
            install_attempted = True
            install = self._run_command(
                ["install", str(apk_path)],
                timeout=min(90, self.command_timeout),
            )

            if "success" not in install.stdout.lower():
                raise SandboxControllerError(
                    "APK installation was not confirmed."
                )
            installed = True

            self._remaining_time(started)

            # Pipe to a bounded collector rather than allowing an unbounded
            # logcat process to write directly to disk.
            log_file = log_path.open("xb")
            log_proc = subprocess.Popen(
                [
                    self.adb_executable,
                    "-s",
                    self.adb_target,
                    "logcat",
                    "-v",
                    "threadtime",
                ],
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            log_stream = log_proc.stdout

            if log_stream is None:
                raise SandboxControllerError(
                    "Unable to open the logcat output stream."
                )

            def collect_bounded_logs() -> None:
                written = 0
                try:
                    while True:
                        chunk = log_stream.read(
                            min(65536, self.max_log_bytes - written + 1)
                        )
                        if not chunk:
                            break

                        remaining_bytes = self.max_log_bytes - written
                        if len(chunk) > remaining_bytes:
                            if remaining_bytes > 0:
                                log_file.write(chunk[:remaining_bytes])
                                written += remaining_bytes
                                log_file.flush()

                            log_limit_hit.set()
                            try:
                                log_proc.kill()
                            except OSError:
                                pass
                            break

                        log_file.write(chunk)
                        written += len(chunk)
                        log_file.flush()

                except BaseException as exc:
                    collector_errors.append(exc)
                    try:
                        log_proc.kill()
                    except OSError:
                        pass

            collector = threading.Thread(
                target=collect_bounded_logs,
                name=f"apk-xray-log-{job_id[:8]}",
                daemon=False,
            )
            collector.start()

            # Give logcat a brief opportunity to establish its stream.
            # This is a startup allowance, not proof that no events were missed.
            time.sleep(min(0.25, self._remaining_time(started)))

            for monkey_args in (
                ["shell", "monkey", "-p", package_name, "1"],
                [
                    "shell",
                    "monkey",
                    "-p",
                    package_name,
                    "--throttle",
                    "100",
                    "200",
                ],
            ):
                if log_limit_hit.is_set():
                    raise SandboxControllerError(
                        "Log output exceeded the configured size limit."
                    )

                remaining = self._remaining_time(started)
                self._run_command(
                    monkey_args,
                    timeout=max(
                        1,
                        min(self.command_timeout, int(remaining)),
                    ),
                )

            # Check whether the collector reached the cap before declaring success.
            if log_limit_hit.is_set():
                raise SandboxControllerError(
                    "Log output exceeded the configured size limit."
                )

        except (
            SandboxControllerError,
            OSError,
            subprocess.TimeoutExpired,
        ) as exc:
            failure_message = str(exc)
            logger.warning(
                "Dynamic-analysis job failed: job_id=%s error_type=%s",
                job_id,
                type(exc).__name__,
            )

        finally:
            if log_proc is not None and collector is not None:
                try:
                    self._stop_logcat(log_proc, collector)
                except SandboxControllerError as exc:
                    cleanup_failed = True
                    failure_message = failure_message or str(exc)

            if log_stream is not None:
                try:
                    log_stream.close()
                except OSError:
                    cleanup_failed = True
                    failure_message = failure_message or (
                        "Unable to close the logcat stream."
                    )

            if log_file is not None:
                try:
                    log_file.close()
                except OSError:
                    cleanup_failed = True
                    failure_message = failure_message or (
                        "Unable to close the log artifact."
                    )

            # An install command can fail after partially changing device state.
            # Attempt uninstall whenever installation was attempted.
            if install_attempted:
                try:
                    self._run_command(
                        ["uninstall", package_name],
                        timeout=min(10, self.command_timeout),
                    )
                except SandboxControllerError:
                    cleanup_failed = True
                    logger.error(
                        "Uninstall failed for job_id=%s; emulator must "
                        "be reset and quarantined before reuse.",
                        job_id,
                    )

            if collector_errors:
                cleanup_failed = True
                failure_message = failure_message or (
                    "Log collection failed."
                )

            if log_limit_hit.is_set():
                failure_message = failure_message or (
                    "Log output exceeded the configured size limit."
                )

            if cleanup_failed:
                failure_message = (
                    "Cleanup failed; emulator must be quarantined and "
                    "reset before reuse."
                )

        if failure_message is None and not cleanup_failed:
            if log_path is None or not log_path.is_file():
                failure_message = "Log artifact was not created."
            elif log_path.stat().st_size > self.max_log_bytes:
                failure_message = (
                    "Collected log exceeded the configured size limit."
                )
            elif not installed:
                failure_message = "APK installation was not confirmed."
            else:
                success_result = {
                    "status": "SUCCESS",
                    "job_id": job_id,
                    "raw_log_path": str(log_path),
                    "message": (
                        "Log collection completed; log contents have not "
                        "yet been analyzed. Emulator reset is still required "
                        "before the instance can be reused."
                    ),
                }

        if success_result is not None:
            return success_result

        return {
            "status": "FAILED",
            "job_id": job_id,
            "error": failure_message or "Dynamic analysis failed.",
        }
