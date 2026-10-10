import io
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from backend.api import app
from backend.gemma import GemmaError


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_rejects_non_apk_and_oversized_uploads(self) -> None:
        response = self.client.post("/api/upload", files={"file": ("notes.txt", b"text", "text/plain")})
        self.assertEqual(response.status_code, 415)
        with patch.dict("os.environ", {"APK_XRAY_MAX_UPLOAD_BYTES": "2"}):
            response = self.client.post("/api/upload", files={"file": ("sample.apk", b"123", "application/vnd.android.package-archive")})
        self.assertEqual(response.status_code, 413)

    def test_returns_schema_validated_report(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("AndroidManifest.xml", b"manifest")
        facts = {
            "app": {"name": None, "packageName": "org.example.app", "version": None, "minSdk": None, "targetSdk": 35, "permissions": [], "components": []},
            "evidence": [{"id": "manifest:package", "label": "Package name", "snippet": "org.example.app", "availability": "available"}],
        }
        with patch("backend.api.parse_apk", return_value=facts):
            with patch.dict(
                "os.environ",
                {"GEMMA4_ENDPOINT": "", "GEMMA4_API_KEY": ""},
            ):
                response = self.client.post(
                    "/api/upload",
                    files={
                        "file": (
                            "sample.apk",
                            archive.getvalue(),
                            "application/vnd.android.package-archive",
                        )
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"]["value"], 0)
        self.assertEqual(response.json()["ai"]["status"], "unavailable")

    def test_returns_valid_report_when_gemma_fails(self) -> None:
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("AndroidManifest.xml", b"manifest")
        facts = {
            "app": {
                "name": None,
                "packageName": "org.example.app",
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
                    "snippet": "org.example.app",
                    "availability": "available",
                }
            ],
        }
        with (
            patch("backend.api.parse_apk", return_value=facts),
            patch.dict(
                "os.environ",
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
            response = self.client.post(
                "/api/upload",
                files={
                    "file": (
                        "sample.apk",
                        archive.getvalue(),
                        "application/vnd.android.package-archive",
                    )
                },
            )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["ai"]["status"], "error")
        self.assertIn("gemma_timeout", report["ai"]["message"])
        self.assertEqual(report["score"]["value"], 0)
        self.assertIn("findings", report)


if __name__ == "__main__":
    unittest.main()
