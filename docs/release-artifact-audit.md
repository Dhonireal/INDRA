# Release Artifact Audit & Checksum Verification

**Project:** VisionPilot  
**Version:** 0.1.0  
**Target Platform:** Windows 11 (x86_64, Windows on ARM compatible via Prism)  
**Date:** October 3, 2026  
**Auditor:** QA & Release Engineer  

---

## 1. Release Artifact Inventory

All release artifacts were built using production pipelines and inspected for integrity, size, and security compliance.

| Artifact Filename | Type | Size | SHA-256 Checksum | Launch Status |
| :--- | :--- | :--- | :--- | :--- |
| `release/VisionPilot-Setup-0.1.0.exe` | Inno Setup Windows Installer | 131.57 MB | `aee0c21bad6e7011ae3fd1c20c5490b497c98ea6e87d1583ead470e1224e4e17` | **VERIFIED** (Installs cleanly into `%LOCALAPPDATA%\Programs\VisionPilot`) |
| `release/VisionPilot-0.1.0-portable.zip` | Standalone Portable Archive | 150.59 MB | `663ef2b73347d3c0bba3777fc1797d0ffbb3ccb0ba11a98fc76b3206edc00646` | **VERIFIED** (Extracts and launches standalone) |
| `dist/VisionPilot/VisionPilot.exe` | PyInstaller Executable | 7.26 MB | Verified build output | **VERIFIED** (Primary entry binary) |
| `release/SHA256SUMS.txt` | Checksum Manifest | 193 B | Verified manifest | **VERIFIED** |
| `release/RELEASE_NOTES.md` | Release Notes | 5.8 KB | Canonical release documentation | **VERIFIED** |

---

## 2. Artifact Hygiene & Content Verification

Each distribution was extracted and audited against the following checklist:
- [x] **Zero Dev Artifacts:** No `.pyc` files, `__pycache__` folders, or `.pytest_cache` directories bundled.
- [x] **Zero Hardcoded Secrets:** No `.env` files, API keys, private tokens, or test databases included.
- [x] **Zero Dev Machine Paths:** No hardcoded developer usernames (`rishi`, `Administrator`) in configuration or packaged binaries.
- [x] **Asset Completeness:** Application icons (`assets/icons/app_icon.ico`, `app_icon.png`), stylesheets, and runtime dependencies correctly bundled.
- [x] **Data Isolation:** User data is strictly directed to `%LOCALAPPDATA%\VisionPilot\data\` at runtime; installer does not touch system directories.
- [x] **Uninstall Cleanliness:** Uninstaller cleanly removes all application binaries and shortcuts, leaving user data intact as expected.

---

## 3. Code Signing & SmartScreen Notice

- **Signing Status:** Unsigned (Open-Source Community Build).
- **Windows SmartScreen Behavior:** Windows Defender SmartScreen may display an *"Unknown Publisher"* warning on first launch.
- **Remediation:** Users and competition evaluators click **More info** -> **Run anyway**. This is standard behavior for open-source submissions without commercial EV code-signing certificates.
