import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from apk_parser import ApkParseError, parse_apk


class ApkParserTests(unittest.TestCase):
    def test_rejects_missing_and_non_archive_inputs(self) -> None:
        with self.assertRaisesRegex(ApkParseError, "not found"):
            parse_apk("missing.apk")
        with tempfile.NamedTemporaryFile(suffix=".apk") as handle:
            handle.write(b"not an apk")
            handle.flush()
            with self.assertRaisesRegex(ApkParseError, "valid ZIP/APK"):
                parse_apk(handle.name)

    def test_normalizes_metadata_components_and_stable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk_path = Path(directory) / "fixture.apk"
            with zipfile.ZipFile(apk_path, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"placeholder")
            fake_apk = Mock()
            fake_apk.get_package.return_value = "org.example.app"
            fake_apk.get_permissions.return_value = ["android.permission.INTERNET"]
            fake_apk.get_activities.return_value = ["org.example.MainActivity"]
            fake_apk.get_services.return_value = []
            fake_apk.get_receivers.return_value = []
            fake_apk.get_providers.return_value = []
            fake_apk.get_android_manifest_xml.return_value = None
            fake_apk.get_app_name.return_value = None
            fake_apk.get_androidversion_name.return_value = None
            fake_apk.get_min_sdk_version.return_value = None
            fake_apk.get_target_sdk_version.return_value = 35
            with patch("androguard.core.apk.APK", return_value=fake_apk):
                first = parse_apk(apk_path)
                second = parse_apk(apk_path)
        self.assertEqual(first, second)
        self.assertEqual(first["app"]["packageName"], "org.example.app")
        self.assertIsNone(first["app"]["name"])
        self.assertIsNone(first["app"]["version"])
        self.assertEqual(first["app"]["targetSdk"], 35)
        self.assertEqual(first["app"]["components"][0]["exported"], None)
        self.assertEqual(first["evidence"][0]["id"], "manifest:package")

    def test_wraps_parser_failures_with_actionable_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            apk_path = Path(directory) / "fixture.apk"
            with zipfile.ZipFile(apk_path, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"placeholder")
            fake_apk = Mock()
            fake_apk.get_package.side_effect = ValueError("bad manifest")
            with patch("androguard.core.apk.APK", return_value=fake_apk):
                with self.assertRaisesRegex(ApkParseError, "Unable to parse APK manifest"):
                    parse_apk(apk_path)


if __name__ == "__main__":
    unittest.main()
