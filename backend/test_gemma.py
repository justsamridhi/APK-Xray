import json
import unittest
import urllib.error
from unittest.mock import patch

from backend.gemma import GemmaError, explain


class GemmaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.facts = {
            "app": {"packageName": "org.example.app", "permissions": [], "components": []},
            "evidence": [
                {
                    "id": "manifest:package",
                    "label": "Package",
                    "snippet": "org.example.app",
                }
            ],
        }

    @staticmethod
    def response(body: bytes):
        return type(
            "Response",
            (),
            {
                "__enter__": lambda self: self,
                "__exit__": lambda *args: None,
                "read": lambda self, _: body,
            },
        )()

    def test_rejects_unknown_evidence_claims(self) -> None:
        generated = {
            "claims": [
                {
                    "text": "claim",
                    "classification": "Can",
                    "evidenceIds": ["unknown"],
                }
            ],
            "explanations": {"en": "e", "hi": "h"},
        }
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(generated)}]}}]}
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            with self.assertRaisesRegex(GemmaError, "unknown evidence"):
                explain("https://example.test", "test-key", self.facts, 1)

    def test_rejects_evidence_map_instead_of_claim_array(self) -> None:
        generated = {
            "claims": {
                "manifest:package": "The package is declared."
            },
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(generated)}]}}]}
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            with self.assertRaisesRegex(GemmaError, "claims_type=dict"):
                explain("https://example.test", "test-key", self.facts, 1)

    def test_sends_google_request_and_parses_markdown_json(self) -> None:
        generated = {
            "claims": [
                {
                    "text": "The package is declared.",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                }
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }
        body = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": f"```json\n{json.dumps(generated)}\n```"}]
                        }
                    }
                ]
            }
        ).encode()
        with patch(
            "urllib.request.urlopen", return_value=self.response(body)
        ) as urlopen:
            result = explain("https://example.test", "test-key", self.facts, 1)
        request = urlopen.call_args.args[0]
        request_body = json.loads(request.data)
        self.assertEqual(request.headers["X-goog-api-key"], "test-key")
        self.assertNotIn("Authorization", request.headers)
        self.assertIn("contents", request_body)
        self.assertIn("parts", request_body["contents"][0])
        self.assertNotIn("role", request_body["contents"][0])
        self.assertIn("text", request_body["contents"][0]["parts"][0])
        self.assertEqual(
            request_body["generationConfig"],
            {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            },
        )
        self.assertNotIn('"output":', request_body["contents"][0]["parts"][0]["text"])
        self.assertIn("Do not use evidence IDs as object keys", request_body["contents"][0]["parts"][0]["text"])
        self.assertEqual(result["claims"][0]["evidenceIds"], ["manifest:package"])

    def test_parses_json_surrounded_by_harmless_text(self) -> None:
        generated = json.dumps(
            {
                "claims": [
                    {
                        "text": "The package is declared.",
                        "classification": "Can",
                        "evidenceIds": ["manifest:package"],
                    }
                ],
                "explanations": {"en": "English", "hi": "हिन्दी"},
            }
        )
        body = json.dumps(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [{"text": f"Here is the result:\n{generated}\nDone."}]
                        },
                    }
                ]
            }
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            result = explain("https://example.test", "test-key", self.facts, 1)
        self.assertEqual(result["claims"][0]["classification"], "Can")

    def test_preserves_multiple_parts_and_accepts_structured_output_wrapper(self) -> None:
        generated = {
            "structured_output": {
                "claims": [
                    {
                        "text": "The package is declared.",
                        "classification": "Can",
                        "evidenceIds": ["manifest:package"],
                    }
                ],
                "explanations": {"en": "English", "hi": "हिन्दी"},
            }
        }
        body = json.dumps(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"text": "The result follows:\n" + json.dumps(generated)[:40]},
                                {"text": json.dumps(generated)[40:]},
                            ]
                        },
                    }
                ]
            }
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            result = explain("https://example.test", "test-key", self.facts, 1)
        self.assertEqual(result["claims"][0]["evidenceIds"], ["manifest:package"])

    def test_rejects_two_competing_top_level_contract_objects(self) -> None:
        generated = {
            "claims": [
                {
                    "text": "The package is declared.",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                }
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }
        body = json.dumps(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        json.dumps(generated)
                                        + "\n"
                                        + json.dumps(generated)
                                    )
                                }
                            ]
                        },
                    }
                ]
            }
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            with self.assertRaisesRegex(GemmaError, "contract_objects=2"):
                explain("https://example.test", "test-key", self.facts, 1)

    def test_ignores_json_looking_text_inside_a_quoted_string(self) -> None:
        nested_text = json.dumps(
            {
                "claims": [],
                "explanations": {"en": "nested", "hi": "नेस्टेड"},
            }
        )
        generated = {
            "claims": [],
            "explanations": {
                "en": f'The note contains {nested_text}',
                "hi": "वास्तविक व्याख्या",
            },
        }
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(generated)}]}}]}
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            result = explain("https://example.test", "test-key", self.facts, 1)
        self.assertEqual(result["claims"], [])

    def test_ignores_thought_part_and_selects_non_thought_response(self) -> None:
        thought = {
            "claims": [
                {
                    "text": "Do not use this thought.",
                    "classification": "Can",
                    "evidenceIds": ["unknown"],
                }
            ],
            "explanations": {"en": "thought", "hi": "विचार"},
        }
        final = {
            "claims": [
                {
                    "text": "The package is declared.",
                    "classification": "Can",
                    "evidenceIds": ["manifest:package"],
                }
            ],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }
        body = json.dumps(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"thought": True, "text": json.dumps(thought)},
                                {"text": json.dumps(final)},
                            ]
                        },
                    }
                ]
            }
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            result = explain("https://example.test", "test-key", self.facts, 1)
        self.assertEqual(result["claims"][0]["evidenceIds"], ["manifest:package"])

    def test_rejects_thought_only_response(self) -> None:
        generated = {
            "claims": [],
            "explanations": {"en": "thought", "hi": "विचार"},
        }
        body = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"thought": True, "text": json.dumps(generated)}]
                        }
                    }
                ]
            }
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            with self.assertRaisesRegex(GemmaError, "non-thought final output"):
                explain("https://example.test", "test-key", self.facts, 1)

    def test_rejects_invalid_generated_json_with_safe_diagnostics(self) -> None:
        body = json.dumps(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "not JSON"}]},
                    }
                ]
            }
        ).encode()
        with patch("urllib.request.urlopen", return_value=self.response(body)):
            with self.assertRaisesRegex(
                GemmaError, r"complete JSON object.*finish_reason=STOP"
            ):
                explain("https://example.test", "test-key", self.facts, 1)

    def test_rejects_http_errors_without_exposing_key(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                "https://example.test", 403, "forbidden", {}, None
            ),
        ):
            with self.assertRaisesRegex(GemmaError, "HTTP 403") as error:
                explain("https://example.test", "secret-key", self.facts, 1)
        self.assertNotIn("secret-key", str(error.exception))

    def test_retries_once_on_timeout_and_uses_configured_timeout(self) -> None:
        generated = {
            "claims": [],
            "explanations": {"en": "English", "hi": "हिन्दी"},
        }
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": json.dumps(generated)}]}}]}
        ).encode()
        with (
            patch.dict("os.environ", {"APK_XRAY_GEMMA_TIMEOUT": "7"}),
            patch(
                "urllib.request.urlopen",
                side_effect=[TimeoutError(), self.response(body)],
            ) as urlopen,
        ):
            result = explain("https://example.test", "test-key", self.facts)
        self.assertEqual(result["claims"], [])
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args_list[0].kwargs["timeout"], 7.0)
        self.assertEqual(urlopen.call_args_list[1].kwargs["timeout"], 7.0)

    def test_timeout_after_retry_has_safe_timeout_code(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError(),
        ) as urlopen:
            with self.assertRaises(GemmaError) as error:
                explain("https://example.test", "test-key", self.facts, 1)
        self.assertEqual(error.exception.code, "gemma_timeout")
        self.assertEqual(urlopen.call_count, 2)

    def test_does_not_retry_contract_failure(self) -> None:
        body = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "not JSON"}]}}]}
        ).encode()
        with patch(
            "urllib.request.urlopen", return_value=self.response(body)
        ) as urlopen:
            with self.assertRaises(GemmaError):
                explain("https://example.test", "test-key", self.facts, 1)
        self.assertEqual(urlopen.call_count, 1)

    def test_rejects_blocked_or_empty_candidate_responses(self) -> None:
        for envelope in ({}, {"promptFeedback": {"blockReason": "SAFETY"}}):
            body = json.dumps(envelope).encode()
            with patch(
                "urllib.request.urlopen", return_value=self.response(body)
            ):
                with self.assertRaisesRegex(GemmaError, "no candidates"):
                    explain("https://example.test", "test-key", self.facts, 1)
