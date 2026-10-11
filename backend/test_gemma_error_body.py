import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from backend.gemma import GemmaError, explain

class GemmaErrorBodyTests(unittest.TestCase):
    def setUp(self):
        self.facts = {
            "app": {"packageName": "org.example.app", "permissions": [], "components": []},
            "evidence": [{"id": "manifest:package", "label": "Package", "snippet": "org.example.app"}],
        }
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemma-4-26b-a4b-it:generateContent"
        self.api_key = "test-key"

    def test_http_400_error_body_is_exposed(self):
        # Simulate a HTTPError 400 with a JSON error body
        error_body = json.dumps({"error": {"code": 400, "message": "Invalid request"}}).encode()
        http_error = urllib.error.HTTPError(
            self.endpoint,
            400,
            "Bad Request",
            {},
            io.BytesIO(error_body),
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaisesRegex(GemmaError, "Gemma request returned HTTP 400") as cm:
                explain(self.endpoint, self.api_key, self.facts, 1)
            # Ensure the error body is included in the message but API key is not leaked
            self.assertIn("Invalid request", str(cm.exception))
            self.assertNotIn(self.api_key, str(cm.exception))
