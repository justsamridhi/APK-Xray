"""FastAPI service for safe, static APK analysis."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .gemma import GemmaError, explain
from .parser import ApkParseError, parse_apk
from .report_builder import build_report
from .report_store import get_report as retrieve_report
from .report_store import save_report
from .sentry_setup import init_sentry, sentry_span

# ---------------------------------------------------------------------------
# Initialise Sentry once at module load with production settings.
# When SENTRY_DSN is absent this is a fast no-op.
# ---------------------------------------------------------------------------
try:
    _startup_settings = load_settings()
    init_sentry(
        _startup_settings.sentry_dsn,
        _startup_settings.sentry_traces_sample_rate,
    )
except ValueError:
    # Config errors are surfaced per-request; don't crash at import time.
    pass

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

            # ------------------------------------------------------------------
            # Stage 1: APK parsing
            # ------------------------------------------------------------------
            with sentry_span("apk.parse", "Parse APK manifest") as span:
                span.set_data("stage", "parse")
                span.set_data("apk_size_bytes", size)
                try:
                    facts = parse_apk(path)
                    span.set_data("outcome", "ok")
                except ApkParseError:
                    span.set_data("outcome", "parse_error")
                    raise

            # ------------------------------------------------------------------
            # Stage 2: Gemma explanation (optional)
            # ------------------------------------------------------------------
            gemma_callable = None
            if settings.gemma_endpoint:
                def gemma_callable(value: dict) -> dict:  # type: ignore[misc]
                    with sentry_span("gemma.explain", "Gemma AI explanation") as gspan:
                        gspan.set_data("stage", "gemma")
                        try:
                            result = explain(
                                settings.gemma_endpoint or "",
                                settings.gemma_api_key,
                                value,
                                settings.gemma_timeout_seconds,
                            )
                            gspan.set_data("outcome", "ok")
                            return result
                        except GemmaError as exc:
                            # Expected failures — graceful degradation preserved.
                            gspan.set_data("outcome", "gemma_error")
                            gspan.set_data("error_category", exc.code)
                            raise

            # ------------------------------------------------------------------
            # Stage 3: Report building (scoring + schema validation)
            # ------------------------------------------------------------------
            with sentry_span("report.build", "Build and validate report") as span:
                span.set_data("stage", "build")
                try:
                    report = build_report(facts, gemma_callable)
                    span.set_data("outcome", "ok")
                except ValueError:
                    span.set_data("outcome", "schema_error")
                    raise

        # ----------------------------------------------------------------------
        # Stage 4: Persist report
        # ----------------------------------------------------------------------
        with sentry_span("report.save", "Persist report to SQLite") as span:
            span.set_data("stage", "save")
            try:
                save_report(report)
                span.set_data("outcome", "ok")
            except (sqlite3.Error, OSError):
                span.set_data("outcome", "storage_error")
                raise

    except ApkParseError as error:
        return _error(422, str(error))
    except ValueError as error:
        return _error(500, str(error))
    except (sqlite3.Error, OSError):
        return _error(500, "The analysis report could not be saved.")

    return JSONResponse(status_code=200, content=report)
