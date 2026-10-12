import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Set environment variables before importing Settings
os.environ['GEMMA4_ENDPOINT'] = 'https://example.com/v1/models/gemma:generateContent'
os.environ['GEMMA4_API_KEY'] = 'dummy-key'

from backend.api import app

client = TestClient(app)

class GemmaConfigTests(unittest.TestCase):
    def setUp(self):
        # Create a minimal valid in‑memory ZIP (APK) fixture.
        import io, zipfile
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("AndroidManifest.xml", "<manifest></manifest>")
        self.sample_apk_bytes = buffer.getvalue()

    @patch('backend.api.parse_apk')
    @patch('backend.api.explain')
    def test_ai_used_when_endpoint_and_key_set(self, mock_explain, mock_parse):
        mock_parse.return_value = {
            'app': {
                'name': None,
                'packageName': 'com.example.app',
                'version': None,
                'minSdk': None,
                'targetSdk': None,
                'permissions': [],
                'components': [],
            },
            'evidence': []
        }
        mock_explain.return_value = {
            'claims': [],
            'explanations': {'en': 'EN explanation', 'hi': 'HI explanation'}
        }
        response = client.post('/api/upload', files={'file': ('test.apk', self.sample_apk_bytes, 'application/octet-stream')})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('ai', data)
        self.assertEqual(data['ai']['status'], 'verified')
        self.assertEqual(data['ai']['provider'], 'Gemma 4')

if __name__ == '__main__':
    unittest.main()
