
"""Unit tests for APK-Xray emulator lifecycle management.

These tests use no real emulator, ADB, or Docker.
"""

import threading
import unittest

from backend.dynamic.emulator_manager import (
    EmulatorLifecycleError,
    EmulatorLifecycleManager,
    EmulatorState,
)


class EmulatorLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = EmulatorLifecycleManager(
            ["emulator-1", "emulator-2"]
        )

    def test_initial_states_are_available(self) -> None:
        states = self.manager.snapshot()
        self.assertEqual(states["emulator-1"], EmulatorState.AVAILABLE)
        self.assertEqual(states["emulator-2"], EmulatorState.AVAILABLE)

    def test_verified_reset_returns_emulator_to_available(self) -> None:
        self.manager.lease("emulator-1", "job-1")
        self.manager.start("emulator-1", "job-1")
        self.manager.begin_reset("emulator-1", "job-1")
        self.manager.complete_reset(
            "emulator-1", "job-1", reset_verified=True
        )

        self.assertEqual(
            self.manager.snapshot()["emulator-1"],
            EmulatorState.AVAILABLE,
        )

    def test_unverified_reset_quarantines_emulator(self) -> None:
        self.manager.lease("emulator-1", "job-1")
        self.manager.start("emulator-1", "job-1")
        self.manager.begin_reset("emulator-1", "job-1")
        self.manager.complete_reset(
            "emulator-1", "job-1", reset_verified=False
        )

        self.assertEqual(
            self.manager.snapshot()["emulator-1"],
            EmulatorState.QUARANTINED,
        )

    def test_emulator_cannot_be_leased_twice(self) -> None:
        self.manager.lease("emulator-1", "job-1")

        with self.assertRaises(EmulatorLifecycleError):
            self.manager.lease("emulator-1", "job-2")

    def test_one_job_cannot_lease_two_emulators(self) -> None:
        self.manager.lease("emulator-1", "job-1")

        with self.assertRaises(EmulatorLifecycleError):
            self.manager.lease("emulator-2", "job-1")

    def test_only_owner_can_start_emulator(self) -> None:
        self.manager.lease("emulator-1", "job-1")

        with self.assertRaises(EmulatorLifecycleError):
            self.manager.start("emulator-1", "job-2")

    def test_cannot_start_without_lease(self) -> None:
        with self.assertRaises(EmulatorLifecycleError):
            self.manager.start("emulator-1", "job-1")

    def test_cannot_complete_reset_before_reset_begins(self) -> None:
        self.manager.lease("emulator-1", "job-1")

        with self.assertRaises(EmulatorLifecycleError):
            self.manager.complete_reset(
                "emulator-1", "job-1", reset_verified=True
            )

    def test_quarantined_emulator_cannot_be_leased(self) -> None:
        self.manager.lease("emulator-1", "job-1")
        self.manager.quarantine("emulator-1", "job-1")

        with self.assertRaises(EmulatorLifecycleError):
            self.manager.lease("emulator-1", "job-2")

    def test_quarantine_removes_active_lease(self) -> None:
        self.manager.lease("emulator-1", "job-1")
        self.manager.quarantine("emulator-1", "job-1")

        with self.assertRaises(EmulatorLifecycleError):
            self.manager.start("emulator-1", "job-1")

    def test_unknown_emulator_is_rejected(self) -> None:
        with self.assertRaises(EmulatorLifecycleError):
            self.manager.lease("unknown-emulator", "job-1")

    def test_empty_pool_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            EmulatorLifecycleManager([])

    def test_duplicate_emulator_ids_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            EmulatorLifecycleManager(["emulator-1", "emulator-1"])

    def test_empty_job_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.lease("emulator-1", " ")

    def test_concurrent_leases_allow_only_one_winner(self) -> None:
        barrier = threading.Barrier(3)
        outcomes: list[str] = []
        outcomes_lock = threading.Lock()

        def attempt_lease(job_id: str) -> None:
            barrier.wait()
            try:
                self.manager.lease("emulator-1", job_id)
                outcome = "leased"
            except EmulatorLifecycleError:
                outcome = "rejected"

            with outcomes_lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=attempt_lease, args=("job-1",)),
            threading.Thread(target=attempt_lease, args=("job-2",)),
        ]

        for thread in threads:
            thread.start()

        barrier.wait()

        for thread in threads:
            thread.join(timeout=3)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(outcomes.count("leased"), 1)
        self.assertEqual(outcomes.count("rejected"), 1)

    def test_snapshot_does_not_change_internal_state(self) -> None:
        snapshot = self.manager.snapshot()
        snapshot["emulator-1"] = EmulatorState.QUARANTINED

        self.assertEqual(
            self.manager.snapshot()["emulator-1"],
            EmulatorState.AVAILABLE,
        )


if __name__ == "__main__":
    unittest.main()
