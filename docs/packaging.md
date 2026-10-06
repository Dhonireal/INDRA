# Production Packaging Architecture — VisionPilot

## 1. Overview
VisionPilot is packaged into a standalone Windows desktop distribution using **PyInstaller 6.22** and **Inno Setup 6.4**. This delivers an enterprise-grade, reproducible build pipeline tailored for Windows 11 on ARM64 (Qualcomm Snapdragon X) and x64 compatible PCs.

---

## 2. Packaging Strategy: One-Folder vs One-File

| Attribute | One-Folder (`--onedir`) [Selected] | One-File (`--onefile`) |
|:---|:---|:---|
| **Startup Latency** | **Fast (< 1s cold start)** | Slow (3-6s due to extracting ~150MB archive to `%TEMP%` on every launch) |
| **PySide6 / Qt6 Reliability** | **High** (all Qt plugins remain in permanent paths) | Medium (transient DLL locking in temp folders) |
| **Disk IO on ARM64 Prism** | **Optimal** (cached direct execution) | High (unpacks hundreds of files into `%TEMP%`) |
| **Installer Integration** | **Direct** (Inno Setup compresses and installs cleanly) | Redundant (installer containing an installer) |

**Conclusion:** One-Folder distribution was selected as the primary production architecture per Phase 12 specifications.

---

## 3. Directory Isolation & Path Separation

VisionPilot strictly separates immutable application binaries from user data:

```
Installed Mode:
├── Application Files (Read-Only):
│   └── C:\Program Files\VisionPilot\ (or %LOCALAPPDATA%\Programs\VisionPilot)
│       ├── VisionPilot.exe
│       ├── _internal\ (PySide6, OpenCV, Python runtime, Qt plugins)
│       └── assets\ (icons, tokens)
│
└── User Data Directory (User-Writable):
    └── %LOCALAPPDATA%\VisionPilot\
        ├── data\visionpilot.db (SQLite WAL Task History & Audit Trail)
        ├── logs\visionpilot.log (Privacy-scrubbed application logs)
        └── models\ (Optional downloaded SLM weights)
```

```
Portable Mode (Self-Contained):
└── <Extracted_Directory>\
    ├── VisionPilot.exe
    ├── portable.txt (Marker activating portable path resolution)
    ├── _internal\
    ├── data\visionpilot.db
    └── logs\visionpilot.log
```

---

## 4. Build Scripts & Automation

The packaging pipeline is automated via PowerShell scripts located in `packaging/scripts/`:

1. **`clean_build.ps1`**: Safely removes previous build artifacts (`build/`, `dist/`, `__pycache__`) without touching user data.
2. **`build_windows.ps1`**:
   - Runs pre-build regression and safety gates (`tests/integration/test_security_adversarial.py`, `tests/unit/test_foundation.py`).
   - Executes PyInstaller specification (`packaging/pyinstaller/VisionPilot.spec`).
   - Packages the distribution into `release/VisionPilot-0.1.0-portable.zip`.
   - Compiles Inno Setup installer into `release/VisionPilot-Setup-0.1.0.exe`.
   - Generates cryptographic SHA-256 manifest in `release/SHA256SUMS.txt`.
3. **`verify_build.ps1`**:
   - Validates executable presence and size.
   - Executes `--check-only` pre-flight verification.
   - Executes `--headless` bootstrap validation.
   - Verifies all release artifacts and checksums.
