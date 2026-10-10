"""Safe APK metadata and manifest parsing."""

from .apk_parser import ApkParseError, parse_apk

__all__ = ["ApkParseError", "parse_apk"]
