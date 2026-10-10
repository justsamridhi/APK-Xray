"""Extract normalized, evidence-linked facts from an APK without executing it."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

ANDROID_NS = "http://schemas.android.com/apk/res/android"
ANDROID_NAME = f"{{{ANDROID_NS}}}name"
ANDROID_EXPORTED = f"{{{ANDROID_NS}}}exported"
ANDROID_PERMISSION = f"{{{ANDROID_NS}}}permission"
COMPONENT_TYPES = (
    ("activity", "activities", "activity"),
    ("service", "services", "service"),
    ("receiver", "receivers", "receiver"),
    ("provider", "providers", "provider"),
)


class ApkParseError(ValueError):
    """Actionable error raised when an APK cannot be safely parsed."""


def _stable_id(prefix: str, value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._:-]+", "-", value.strip()).strip("-")
    if not normalized:
        normalized = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{normalized[:110]}"


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _call_optional(apk: Any, method_name: str) -> Any:
    try:
        return getattr(apk, method_name)()
    except (KeyError, TypeError, ValueError):
        return None


def _manifest_elements(manifest: Any, local_name: str) -> Iterable[Any]:
    if manifest is None:
        return ()
    return (
        element
        for element in manifest.iter()
        if str(element.tag).rsplit("}", 1)[-1] == local_name
    )


def _component_facts(apk: Any, manifest: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    components: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for component_type, method_name, tag_name in COMPONENT_TYPES:
        names = set(_call_optional(apk, f"get_{method_name}") or [])
        for element in _manifest_elements(manifest, tag_name):
            name = _optional_string(element.attrib.get(ANDROID_NAME))
            if name:
                names.add(name)
        for name in sorted(names):
            component_id = _stable_id(f"manifest:{component_type}", name)
            exported_value = None
            permission = _optional_string(
                next(
                    (
                        element.attrib.get(ANDROID_PERMISSION)
                        for element in _manifest_elements(manifest, tag_name)
                        if element.attrib.get(ANDROID_NAME) == name
                    ),
                    None,
                )
            )
            for element in _manifest_elements(manifest, tag_name):
                if element.attrib.get(ANDROID_NAME) == name:
                    raw_exported = element.attrib.get(ANDROID_EXPORTED)
                    if raw_exported is not None:
                        exported_value = raw_exported.lower() == "true"
                    break
            components.append(
                {
                    "id": component_id,
                    "type": component_type,
                    "name": name,
                    "exported": exported_value,
                    "permission": permission,
                }
            )
            evidence.append(
                {
                    "id": component_id,
                    "label": f"{component_type}: {name}",
                    "snippet": f"exported={exported_value}",
                    "availability": "available",
                }
            )
    return components, evidence


def parse_apk(path: str | Path) -> dict[str, Any]:
    """Return normalized APK facts and stable evidence references.

    The APK is treated as an archive and parsed by Androguard; no package
    installer, subprocess, emulator, or application code is invoked.
    """

    apk_path = Path(path)
    if not apk_path.is_file():
        raise ApkParseError(f"APK file not found: {apk_path}")
    if apk_path.stat().st_size == 0:
        raise ApkParseError("APK file is empty.")
    if not zipfile.is_zipfile(apk_path):
        raise ApkParseError("Input is not a valid ZIP/APK archive.")
    try:
        with zipfile.ZipFile(apk_path) as archive:
            if archive.testzip() is not None:
                raise ApkParseError(
                    "APK archive is truncated or contains a corrupt entry."
                )
    except (OSError, zipfile.BadZipFile) as error:
        raise ApkParseError(f"Unable to read APK archive: {error}") from error

    try:
        from androguard.core.apk import APK
    except ImportError as error:
        raise ApkParseError(
            "Androguard is not installed; install it with "
            "`python -m pip install -r backend\\requirements-validation.txt`."
        ) from error

    try:
        apk = APK(str(apk_path), testzip=True)
        package_name = _optional_string(apk.get_package())
        if not package_name:
            raise ApkParseError("AndroidManifest.xml does not declare a package name.")
        permissions = sorted(
            permission
            for permission in (apk.get_permissions() or [])
            if isinstance(permission, str) and permission.strip()
        )
        permission_evidence = [
            {
                "id": _stable_id("manifest:permission", permission),
                "label": permission,
                "snippet": permission,
                "availability": "available",
            }
            for permission in permissions
        ]
        components, component_evidence = _component_facts(
            apk, apk.get_android_manifest_xml()
        )
        app_name = _optional_string(_call_optional(apk, "get_app_name"))
        version = _optional_string(_call_optional(apk, "get_androidversion_name"))
        app = {
            "name": app_name,
            "packageName": package_name,
            "version": version,
            "minSdk": _optional_int(_call_optional(apk, "get_min_sdk_version")),
            "targetSdk": _optional_int(_call_optional(apk, "get_target_sdk_version")),
            "permissions": permissions,
            "components": components,
        }
        return {
            "app": app,
            "evidence": [
                {
                    "id": "manifest:package",
                    "label": "Package name",
                    "snippet": package_name,
                    "availability": "available",
                },
                *permission_evidence,
                *component_evidence,
            ],
        }
    except ApkParseError:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ApkParseError(f"Unable to parse APK manifest: {error}") from error
