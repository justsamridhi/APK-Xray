# APK validation fixture

Place a small, non-sensitive APK fixture in this directory as
`sample.apk`, then run:

```powershell
python backend\validation\validate_integrations.py --apk backend\validation\fixtures\sample.apk
```

The fixture must be a real compiled APK with a binary
`AndroidManifest.xml`. A ZIP containing a plain-text manifest is intentionally
not accepted because it would not validate the actual Androguard extraction
boundary. Do not commit proprietary or user-submitted APKs here.
