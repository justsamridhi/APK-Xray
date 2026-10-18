
"""Safe emulator lifecycle state management for APK-Xray.

This module tracks lifecycle state only. It does not connect to ADB,
launch emulators, restore snapshots, or execute APKs.
"""

from __future__ import annotations

import threading
from enum import Enum


class EmulatorState(str, Enum):
    AVAILABLE = "available"
    LEASED = "leased"
    RUNNING = "running"
    RESETTING = "resetting"
    QUARANTINED = "quarantined"


class EmulatorLifecycleError(RuntimeError):
    """Raised when an emulator lifecycle transition is invalid."""


class EmulatorLifecycleManager:
    """Thread-safe lifecycle state manager for emulator identifiers."""

    def __init__(self, emulator_ids: list[str]) -> None:
        if not emulator_ids:
            raise ValueError("At least one emulator ID is required.")

        if any(not item.strip() for item in emulator_ids):
            raise ValueError("Emulator IDs cannot be empty.")

        if len(set(emulator_ids)) != len(emulator_ids):
            raise ValueError("Emulator IDs must be unique.")

        self._lock = threading.Lock()
        self._states = {
            emulator_id: EmulatorState.AVAILABLE
            for emulator_id in emulator_ids
        }
        self._jobs: dict[str, str] = {}

    def snapshot(self) -> dict[str, EmulatorState]:
        """Return a copy of current emulator states."""
        with self._lock:
            return self._states.copy()

    def lease(self, emulator_id: str, job_id: str) -> None:
        """Exclusively assign an available emulator to one job."""
        with self._lock:
            self._require_emulator(emulator_id)

            if not job_id.strip():
                raise ValueError("Job ID cannot be empty.")

            if self._states[emulator_id] != EmulatorState.AVAILABLE:
                raise EmulatorLifecycleError(
                    "Only an available emulator can be leased."
                )

            if job_id in self._jobs:
                raise EmulatorLifecycleError(
                    "This job already holds an emulator lease."
                )

            self._states[emulator_id] = EmulatorState.LEASED
            self._jobs[job_id] = emulator_id

    def start(self, emulator_id: str, job_id: str) -> None:
        """Mark a leased emulator as running."""
        with self._lock:
            self._require_owner(emulator_id, job_id)

            if self._states[emulator_id] != EmulatorState.LEASED:
                raise EmulatorLifecycleError(
                    "Only a leased emulator can start."
                )

            self._states[emulator_id] = EmulatorState.RUNNING

    def begin_reset(self, emulator_id: str, job_id: str) -> None:
        """Move a leased or running emulator into reset."""
        with self._lock:
            self._require_owner(emulator_id, job_id)

            if self._states[emulator_id] not in {
                EmulatorState.LEASED,
                EmulatorState.RUNNING,
            }:
                raise EmulatorLifecycleError(
                    "Only a leased or running emulator can be reset."
                )

            self._states[emulator_id] = EmulatorState.RESETTING

    def complete_reset(
        self,
        emulator_id: str,
        job_id: str,
        *,
        reset_verified: bool,
    ) -> None:
        """Release only after reset verification; otherwise quarantine."""
        with self._lock:
            self._require_owner(emulator_id, job_id)

            if self._states[emulator_id] != EmulatorState.RESETTING:
                raise EmulatorLifecycleError(
                    "The emulator must be resetting before completion."
                )

            if reset_verified:
                self._states[emulator_id] = EmulatorState.AVAILABLE
            else:
                self._states[emulator_id] = EmulatorState.QUARANTINED

            del self._jobs[job_id]

    def quarantine(self, emulator_id: str, job_id: str) -> None:
        """Remove a failed emulator from service."""
        with self._lock:
            self._require_owner(emulator_id, job_id)
            self._states[emulator_id] = EmulatorState.QUARANTINED
            del self._jobs[job_id]

    def _require_emulator(self, emulator_id: str) -> None:
        if emulator_id not in self._states:
            raise EmulatorLifecycleError("Unknown emulator ID.")

    def _require_owner(self, emulator_id: str, job_id: str) -> None:
        self._require_emulator(emulator_id)

        if self._jobs.get(job_id) != emulator_id:
            raise EmulatorLifecycleError(
                "This job does not own the emulator lease."
            )
