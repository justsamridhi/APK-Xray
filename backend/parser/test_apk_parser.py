import tempfile
import unittest
import zipfile
from xml.etree import ElementTree
from pathlib import Path
from unittest.mock import Mock, patch

from apk_parser import ANDROID_NS, ApkParseError, _component_facts, parse_apk


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
        self.assertFalse(first["app"]["components"][0]["exported"])
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

    def test_derives_exported_defaults_and_inherited_permissions(self) -> None:
        manifest = ElementTree.fromstring(
            f'''<manifest xmlns:android="{ANDROID_NS}"><application android:permission="org.example.GUARD">
                <activity android:name="Explicit" android:exported="false"><intent-filter /></activity>
                <activity android:name="Implicit"><intent-filter>
                    <action android:name="android.intent.action.MAIN" />
                    <category android:name="android.intent.category.LAUNCHER" />
                </intent-filter></activity>
                <service android:name="Private" />
                <provider android:name="LegacyProvider" />
            </application></manifest>'''
        )
        apk = Mock()
        apk.get_activities.return_value = ["Explicit", "Implicit"]
        apk.get_services.return_value = ["Private"]
        apk.get_receivers.return_value = []
        apk.get_providers.return_value = ["LegacyProvider"]
        components, _ = _component_facts(apk, manifest, 16)
        by_name = {component["name"]: component for component in components}
        self.assertFalse(by_name["Explicit"]["exported"])
        self.assertTrue(by_name["Implicit"]["exported"])
        self.assertTrue(by_name["Implicit"]["isLauncher"])
        self.assertFalse(by_name["Private"]["exported"])
        self.assertTrue(by_name["LegacyProvider"]["exported"])
        self.assertEqual(by_name["Implicit"]["permission"], "org.example.GUARD")
        self.assertEqual(by_name["Implicit"]["permissionSource"], "application")

    def test_provider_default_is_unknown_without_target_sdk(self) -> None:
        manifest = ElementTree.fromstring(f'<manifest xmlns:android="{ANDROID_NS}"><application><provider android:name="Provider" /></application></manifest>')
        apk = Mock()
        apk.get_activities.return_value = []
        apk.get_services.return_value = []
        apk.get_receivers.return_value = []
        apk.get_providers.return_value = ["Provider"]
        components, _ = _component_facts(apk, manifest, None)
        self.assertIsNone(components[0]["exported"])


if __name__ == "__main__":
    unittest.main()
