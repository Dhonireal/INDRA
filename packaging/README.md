# VisionPilot Packaging & Windows Deployment

This directory contains the production packaging specifications, installer definitions, and automation scripts for distributing VisionPilot on Windows 11 (Qualcomm Snapdragon X and x64 compatible PCs).

---

## Directory Layout

```
packaging/
├── pyinstaller/
│   ├── VisionPilot.spec      # PyInstaller one-folder specification
│   └── hooks/                # Custom PyInstaller runtime hooks (if needed)
├── installer/
│   └── VisionPilot.iss       # Inno Setup 6 installer script
├── scripts/
│   ├── build_windows.ps1     # Unified production build script
│   ├── clean_build.ps1       # Safe build output cleanup script
│   └── verify_build.ps1      # Post-build integrity and startup verification script
└── README.md                 # This documentation
```

---

## Building VisionPilot for Windows

### Prerequisites
1. **Python 3.10+** (Python 3.14 on Windows 11 ARM64 via Prism or Native ARM64).
2. **PyInstaller 6.x**:
   ```powershell
   python -m pip install pyinstaller
   ```
3. **Inno Setup 6** (for `.exe` setup installer generation):
   - Inno Setup compiler (`ISCC.exe`) is automatically discovered from common locations or IDE toolchains.

### Running the Build Pipeline
To execute the complete production packaging pipeline (clean, pre-build test validation, PyInstaller compile, portable ZIP archive generation, Inno Setup compilation, and SHA-256 checksum generation):

```powershell
powershell -ExecutionPolicy Bypass -File packaging/scripts/build_windows.ps1
```

### Verifying the Build
After building, run the automated verification script:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/scripts/verify_build.ps1
```

---

## Generated Release Artifacts

All distributable artifacts are emitted to the `release/` directory:
- `VisionPilot-Setup-0.1.0.exe`: Standard Windows Installer with Start Menu and optional Desktop shortcuts.
- `VisionPilot-0.1.0-portable.zip`: Standalone portable distribution that runs without installation.
- `SHA256SUMS.txt`: Cryptographic SHA-256 checksums for each release file.
- `RELEASE_NOTES.md`: Release notes, platform compatibility, and installation instructions.
