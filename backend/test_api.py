import io
import os
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import app
from backend.gemma import GemmaError
from backend.parser import ApkParseError


def archive_bytes(
    entries: dict[str, bytes], compression: int = zipfile.ZIP_STORED
) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=compression) as output:
        for name, content in entries.items():
            output.writestr(name, content)
    return archive.getvalue()


def facts(package_name: str) -> dict[str, object]:
    return {
        "app": {
            "name": None,
            "packageName": package_name,
            "version": None,
            "minSdk": None,
            "targetSdk": 35,
            "permissions": [],
            "components": [],
        },
        "evidence": [
            {
                "id": "manifest:package",
                "label": "Package name",
                "snippet": package_name,
                "availability": "available",
            }
        ],
    }


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.valid_archive = archive_bytes({"AndroidManifest.xml": b"manifest"})

    def upload(self, content: bytes | None = None):
        return self.client.post(
            "/api/upload",
            files={
                "file": (
                    "sample.apk",
                    self.valid_archive if content is None else content,
                    "application/vnd.android.package-archive",
                )
            },
        )

    def test_rejects_non_apk_and_oversized_uploads(self) -> None:
        response = self.client.post(
            "/api/upload", files={"file": ("notes.txt", b"text", "text/plain")}
        )
        self.assertEqual(response.status_code, 415)
        with patch.dict(os.environ, {"APK_XRAY_MAX_UPLOAD_BYTES": "2"}):
            response = self.upload(b"123")
        self.assertEqual(response.status_code, 413)

    def test_returns_schema_validated_report(self) -> None:
        with (
            patch("backend.api.parse_apk", return_value=facts("org.example.app")),
            patch.dict(os.environ, {"GEMMA4_ENDPOINT": "", "GEMMA4_API_KEY": ""}),
        ):
            response = self.upload()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"]["value"], 0)
        self.assertEqual(response.json()["ai"]["status"], "unavailable")

    def test_upload_responses_are_isolated_without_a_shared_report_endpoint(self) -> None:
        with (
            patch(
                "backend.api.parse_apk",
                side_effect=[facts("org.example.first"), facts("org.example.second")],
            ),
            patch.dict(os.environ, {"GEMMA4_ENDPOINT": "", "GEMMA4_API_KEY": ""}),
        ):
            first = self.upload()
            second = self.upload()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["app"]["packageName"], "org.example.first")
        self.assertEqual(second.json()["app"]["packageName"], "org.example.second")
        self.assertEqual(self.client.get("/api/report").status_code, 404)

    def test_rejects_unsafe_archive_paths_before_parsing(self) -> None:
        unsafe_archive = archive_bytes({"../outside.txt": b"unsafe"})
        with patch("backend.api.parse_apk") as parse:
            response = self.upload(unsafe_archive)
        self.assertEqual(response.status_code, 422)
        self.assertIn("unsafe entry path", response.json()["error"]["message"])
        parse.assert_not_called()

    def test_rejects_malformed_archives_before_parsing(self) -> None:
        with patch("backend.api.parse_apk") as parse:
            response = self.upload(b"not a zip archive")
        self.assertEqual(response.status_code, 422)
        self.assertIn("malformed or unreadable", response.json()["error"]["message"])
        parse.assert_not_called()

    def test_rejects_archives_with_corrupt_entries_before_parsing(self) -> None:
        corrupt_archive = bytearray(self.valid_archive)
        content_index = corrupt_archive.index(b"manifest")
        corrupt_archive[content_index] ^= 1
        with patch("backend.api.parse_apk") as parse:
            response = self.upload(bytes(corrupt_archive))
        self.assertEqual(response.status_code, 422)
        self.assertIn("corrupt entry", response.json()["error"]["message"])
        parse.assert_not_called()

    def test_rejects_entry_count_expanded_size_and_compression_ratio_limits(self) -> None:
        with patch("backend.api.parse_apk") as parse:
            with patch.dict(os.environ, {"APK_XRAY_MAX_ZIP_ENTRIES": "1"}):
                response = self.upload(
                    archive_bytes({"AndroidManifest.xml": b"manifest", "classes.dex": b"dex"})
                )
            self.assertEqual(response.status_code, 422)
            self.assertIn("too many entries", response.json()["error"]["message"])

            with patch.dict(os.environ, {"APK_XRAY_MAX_ENTRY_UNCOMPRESSED_BYTES": "4"}):
                response = self.upload()
            self.assertEqual(response.status_code, 422)
            self.assertIn("entry exceeds", response.json()["error"]["message"])

            with patch.dict(os.environ, {"APK_XRAY_MAX_TOTAL_UNCOMPRESSED_BYTES": "10"}):
                response = self.upload(
                    archive_bytes({"AndroidManifest.xml": b"123456", "classes.dex": b"123456"})
                )
            self.assertEqual(response.status_code, 422)
            self.assertIn("total expanded", response.json()["error"]["message"])

            with patch.dict(os.environ, {"APK_XRAY_MAX_COMPRESSION_RATIO": "2"}):
                response = self.upload(
                    archive_bytes(
                        {"AndroidManifest.xml": b"0" * 8_192}, zipfile.ZIP_DEFLATED
                    )
                )
            self.assertEqual(response.status_code, 422)
            self.assertIn("compression ratio", response.json()["error"]["message"])
        parse.assert_not_called()

    def test_temporary_upload_is_cleaned_after_success_and_failure(self) -> None:
        success_path: Path | None = None

        def successful_parse(path: Path) -> dict[str, object]:
            nonlocal success_path
            success_path = path
            self.assertTrue(path.is_file())
            return facts("org.example.cleanup")

        with (
            patch("backend.api.parse_apk", side_effect=successful_parse),
            patch.dict(os.environ, {"GEMMA4_ENDPOINT": "", "GEMMA4_API_KEY": ""}),
        ):
            self.assertEqual(self.upload().status_code, 200)
        self.assertIsNotNone(success_path)
        self.assertFalse(success_path.parent.exists())

        failure_path: Path | None = None

        def failing_parse(path: Path) -> None:
            nonlocal failure_path
            failure_path = path
            self.assertTrue(path.is_file())
            raise ApkParseError("fixture parser failure")

        with patch("backend.api.parse_apk", side_effect=failing_parse):
            response = self.upload()
        self.assertEqual(response.status_code, 422)
        self.assertIsNotNone(failure_path)
        self.assertFalse(failure_path.parent.exists())

    def test_returns_valid_report_when_gemma_fails(self) -> None:
        with (
            patch("backend.api.parse_apk", return_value=facts("org.example.app")),
            patch.dict(
                os.environ,
                {
                    "GEMMA4_ENDPOINT": "https://example.test/generateContent",
                    "GEMMA4_API_KEY": "test-only-key",
                },
            ),
            patch(
                "backend.api.explain",
                side_effect=GemmaError("Gemma request timed out.", code="gemma_timeout"),
            ),
        ):
            response = self.upload()
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["ai"]["status"], "error")
        self.assertIn("gemma_timeout", report["ai"]["message"])
        self.assertEqual(report["score"]["value"], 0)
        self.assertIn("findings", report)


if __name__ == "__main__":
    unittest.main()
