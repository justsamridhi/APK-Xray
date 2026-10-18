
"""Persistent storage for APK-Xray analysis reports."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def _database_path() -> Path:
    configured_path = os.getenv("APK_XRAY_REPORT_DB_PATH")

    if configured_path:
        return Path(configured_path).expanduser()

    return Path(__file__).resolve().parent.parent / "data" / "reports.sqlite3"


def _connect() -> sqlite3.Connection:
    database_path = _database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path, timeout=10)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
        return connection
    except Exception:
        connection.close()
        raise


def save_report(report: dict[str, Any]) -> None:
    """Persist a report under its unique report ID."""
    report_id = report.get("reportId")
    created_at = report.get("generatedAt")

    if not isinstance(report_id, str) or not report_id.strip():
        raise ValueError("Cannot store a report without a valid report ID.")

    if not isinstance(created_at, str) or not created_at.strip():
        raise ValueError(
            "Cannot store a report without a generation timestamp."
        )

    serialized_report = json.dumps(report, ensure_ascii=False)

    with closing(_connect()) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO reports (report_id, report_json, created_at)
                VALUES (?, ?, ?)
                """,
                (report_id, serialized_report, created_at),
            )


def get_report(report_id: str) -> dict[str, Any] | None:
    """Retrieve one report by its exact ID."""
    with closing(_connect()) as connection:
        row = connection.execute(
            "SELECT report_json FROM reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()

    if row is None:
        return None

    report = json.loads(row[0])

    if not isinstance(report, dict):
        raise ValueError("Stored report has an invalid format.")

    return report
