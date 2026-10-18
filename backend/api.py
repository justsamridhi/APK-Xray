
"""FastAPI service for safe, static APK analysis."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .gemma import explain
from .parser import ApkParseError, parse_apk
from .report_builder import build_report
from .report_store import get_report as retrieve_report
from .report_store import save_report

app = FastAPI(title="APK-Xray API", version="1.0")


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": "analysis_error",
                "message": message,
            }
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/report")
def get_report_without_id() -> JSONResponse:
    return _error(
        400,
        "A report ID is required to retrieve an analysis report.",
    )


@app.get("/api/report/{report_id}")
def get_report(report_id: str) -> JSONResponse:
    try:
        report = retrieve_report(report_id)
    except (sqlite3.Error, OSError, ValueError):
        return _error(500, "The report could not be retrieved.")

    if report is None:
        return _error(404, "No report exists with that ID.")

    return JSONResponse(status_code=200, content=report)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> JSONResponse:
    try:
        settings: Settings = load_settings()
    except ValueError as error:
        return _error(500, str(error))

    if not file.filename or not file.filename.lower().endswith(".apk"):
        return _error(415, "Only files with an .apk extension are accepted.")

    if file.content_type not in {
        None,
        "",
        "application/vnd.android.package-archive",
        "application/octet-stream",
    }:
        return _error(415, "The uploaded file is not an APK.")

    try:
        with tempfile.TemporaryDirectory(prefix="apk-xray-") as directory:
            path = Path(directory) / "upload.apk"
            size = 0

            with path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)

                    if size > settings.max_upload_bytes:
                        return _error(
                            413,
                            "The APK exceeds the configured upload size limit.",
                        )

                    output.write(chunk)

            facts = parse_apk(path)
            gemma = None

            if settings.gemma_endpoint:
                gemma = lambda value: explain(
                    settings.gemma_endpoint or "",
                    settings.gemma_api_key,
                    value,
                    settings.gemma_timeout_seconds,
                )

            report = build_report(facts, gemma)

        save_report(report)

    except ApkParseError as error:
        return _error(422, str(error))
    except ValueError as error:
        return _error(500, str(error))
    except (sqlite3.Error, OSError):
        return _error(500, "The analysis report could not be saved.")

    return JSONResponse(status_code=200, content=report)
