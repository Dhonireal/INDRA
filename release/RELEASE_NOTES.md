# VisionPilot v0.1.0 — Release Notes

**Release Date:** 2026-10-03  
**Tagline:** "See. Understand. Act. Verify."  
**Platform:** Windows 11 on Snapdragon X (ARM64 via Windows on ARM Prism Emulation and x64 compatible PCs)  
**Distribution:** Portable Standalone ZIP & Windows Standard Setup Installer

---

## 1. Overview
VisionPilot is a privacy-first visual computer-use AI agent designed for Windows Snapdragon AI PCs. Operating on a strict **Listen → See → Understand → Plan → Act → Verify** feedback loop, VisionPilot enables local natural language automation of everyday computing tasks while ensuring user privacy, deterministic safety boundaries, and independent state verification.

---

## 2. Release Deliverables

| Artifact | Size | SHA-256 Checksum | Description |
|:---|:---:|:---|:---|
| **`VisionPilot-Setup-0.1.0.exe`** | ~131.6 MB | `aee0c21bad6e7011ae3fd1c20c5490b497c98ea6e87d1583ead470e1224e4e17` | Full Windows Setup Installer with Start Menu and optional Desktop shortcuts. Safe uninstallation preserves user history. |
| **`VisionPilot-0.1.0-portable.zip`** | ~150.6 MB | `663ef2b73347d3c0bba3777fc1797d0ffbb3ccb0ba11a98fc76b3206edc00646` | Standalone portable archive. Unpack and launch without system installation or administrative privileges. |
| **`SHA256SUMS.txt`** | < 1 KB | Verified | Cryptographic verification manifest. |

---

## 3. Core Features & Capabilities

- **Desktop GUI (`PySide6`):** Modern dark/light themed interface with Command Input, real-time Task Progress Panel, History Drawer, and Multi-tab Settings.
- **Natural Language Task Decomposition:** Local-first reasoning engine converts high-level natural language instructions into structured, executable plans without cloud dependencies.
- **Dual-Layer Screen Perception:** Combines native Windows UI Automation (UIA) tree inspection with local Windows Media OCR, prioritizing semantic controls over raw coordinates.
- **Multi-Tier Safety Gate:** Actions classified into `SAFE`, `LOW`, `MEDIUM`, `HIGH`, and `BLOCKED`. Permanent file deletion and bulk destructive commands are strictly blocked.
- **Independent State Verification:** Every completed action is independently verified against the operating system (e.g. confirming destination file existence and source removal) rather than relying on executor return codes.
- **Fault-Tolerant Recovery:** Transient discrepancies automatically trigger re-perception and bounded recovery cycles (max depth = 2) to eliminate infinite loops.
- **Local SQLite History & Audit Trail:** Write-Ahead Logging (WAL) database stores command requests, execution traces, verification outcomes, and audit logs. Interrupted tasks are cleanly flagged upon restart without auto-resuming side effects.
- **Privacy-First Architecture:** Automatic credential redaction (`<redacted:token>`, `<redacted:credential>`), push-to-talk voice capture with zero raw audio persistence, and zero external telemetry.

---

## 4. Hardware Acceleration & Snapdragon X Support

- **Processor Support:** Qualcomm Snapdragon X Elite, Snapdragon X Plus, and x86-64 PCs running Windows 11 (Build 22621+).
- **GPU & NPU Detection:** Automatically detects Qualcomm Adreno GPU and Qualcomm Hexagon NPU.
- **Truthfulness Policy (Rule 3):** Under the current Python 3.14 Prism runtime, hardware status is reported honestly as `DETECTED / NOT VERIFIED` with safe fallback to `CPU_ONLY` / `LocalReasoningEngine`. Zero synthetic NPU acceleration is claimed.

---

## 5. System Requirements

- **Operating System:** Windows 11 (64-bit, ARM64 or x86-64).
- **RAM:** 8 GB minimum (16 GB recommended).
- **Disk Space:** 500 MB free storage for application binaries and local SQLite history.
- **Display:** 1080p (1920x1080) or higher display recommended.

---

## 6. Installation & Removal

### Installing via Setup Executable
1. Download `VisionPilot-Setup-0.1.0.exe`.
2. Run the installer. By default, it installs to `%LOCALAPPDATA%\Programs\VisionPilot` (or `Program Files` with admin elevation).
3. Check the box if you desire a Desktop shortcut.
4. Launch VisionPilot from the Start Menu.

### Using the Portable Archive
1. Download `VisionPilot-0.1.0-portable.zip`.
2. Extract the archive into any user folder.
3. Launch `VisionPilot.exe`. All data and logs remain self-contained within the extracted directory.

### Uninstallation
- Run "Uninstall VisionPilot" from Windows Settings > Installed Apps or Start Menu.
- Application binaries are cleanly removed. User task history in `%LOCALAPPDATA%\VisionPilot` is safely preserved by design.
