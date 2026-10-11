"""FastAPI service for safe, static APK analysis."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from .config import Settings, load_settings
from .gemma import explain
from .parser import ApkParseError, parse_apk
from .report_builder import build_report

app = FastAPI(title="APK-Xray API", version="1.0")


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": "analysis_error", "message": message}},
    )


def _unsafe_archive_path(filename: str) -> bool:
    """Return whether an entry name could escape an extraction directory."""
    normalized = filename.replace("\\", "/")
    return (
        normalized.startswith("/")
        or normalized.startswith("//")
        or (len(normalized) >= 3 and normalized[0].isalpha() and normalized[1:3] == ":/")
        or ".." in normalized.split("/")
    )


def _validate_archive(path: Path, settings: Settings) -> None:
    """Inspect ZIP metadata before handing an untrusted APK to Androguard."""
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > settings.max_zip_entries:
                raise ApkParseError("APK archive contains too many entries.")

            total_uncompressed = 0
            total_compressed = 0
            for entry in entries:
                if _unsafe_archive_path(entry.filename):
                    raise ApkParseError("APK archive contains unsafe entry path.")
                if entry.file_size > settings.max_entry_uncompressed_bytes:
                    raise ApkParseError(
                        "APK entry exceeds the maximum allowed expanded size."
                    )

                total_uncompressed += entry.file_size
                total_compressed += entry.compress_size
                if total_uncompressed > settings.max_total_uncompressed_bytes:
                    raise ApkParseError(
                        "APK archive exceeds the maximum total expanded size."
                    )
                if entry.file_size and entry.compress_size == 0:
                    raise ApkParseError(
                        "APK archive contains an entry with a suspicious compression ratio."
                    )
                if (
                    entry.compress_size
                    and entry.file_size / entry.compress_size
                    > settings.max_compression_ratio
                ):
                    raise ApkParseError(
                        "APK archive contains an entry with a suspicious compression ratio."
                    )

            if total_uncompressed and total_compressed == 0:
                raise ApkParseError("APK archive has a suspicious compression ratio.")
            if (
                total_compressed
                and total_uncompressed / total_compressed
                > settings.max_compression_ratio
            ):
                raise ApkParseError("APK archive has a suspicious compression ratio.")
            if archive.testzip() is not None:
                raise ApkParseError("APK archive contains a corrupt entry.")
    except (OSError, zipfile.BadZipFile) as error:
        raise ApkParseError("APK archive is malformed or unreadable.") from error


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> JSONResponse:
    try:
        settings = load_settings()
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
                            413, "The APK exceeds the configured upload size limit."
                        )
                    output.write(chunk)

            _validate_archive(path, settings)
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
            return JSONResponse(status_code=200, content=report)
    except ApkParseError as error:
        return _error(422, str(error))
    except OSError:
        return _error(500, "The upload could not be processed safely.")
    except ValueError as error:
        return _error(500, str(error))
    finally:
        await file.close()
