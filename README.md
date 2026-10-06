# VisionPilot

> **Privacy-First Visual Computer-Use AI Agent for Windows Snapdragon AI PCs**  
> *"See. Understand. Act. Verify."*

---

## 1. Overview

**VisionPilot** is an open-source, local-first visual computer-use AI desktop agent built specifically for Windows 11 and Snapdragon AI PCs. 

Operating on a closed feedback loop:
```
Listen → See → Understand → Plan → Act → Verify
```
VisionPilot empowers users to automate desktop tasks using natural language voice and text commands while enforcing strict privacy, zero always-on listening, deterministic safety gates, and independent post-action state verification.

---

## 2. Key Features

- **Local-First Architecture:** Operates entirely offline without mandatory cloud connections or remote telemetry.
- **Dual-Layer Screen Grounding:** Combines Windows UI Automation (UIA) control hierarchy with local Windows Media OCR, avoiding fragile hardcoded coordinates.
- **Deterministic Action Planning:** Structured plan decomposition with strict JSON schemas and validation that categorically rejects arbitrary code execution.
- **Multi-Tier Safety Gate:** Actions classified as `SAFE`, `LOW`, `MEDIUM`, `HIGH`, or `BLOCKED`. Permanent file deletion and bulk destructive operations are strictly blocked.
- **Independent State Verification:** Validates actual system state (e.g. file creation, window activation, element disappearance) rather than relying on executor return codes.
- **Resilient Recovery Engine:** Transient discrepancies trigger re-perception and bounded recovery cycles (max depth = 2) to prevent infinite loops.
- **Encrypted & Redacted Task History:** SQLite Write-Ahead Logging (WAL) database storing complete execution and audit trails with automatic secret redaction (`<redacted:token>`, `<redacted:credential>`).
- **Modern PySide6 Desktop GUI:** Sleek dark/light themed interface with Command Input, real-time Task Progress Panel, History Drawer, and Hardware Telemetry.

---

## 3. Supported Platforms & Snapdragon AI PC Positioning

- **Operating System:** Windows 11 (64-bit, ARM64 or x86-64).
- **Hardware Architecture:** Qualcomm Snapdragon X Elite, Snapdragon X Plus, and compatible x86-64 PCs.
- **Snapdragon Positioning:** VisionPilot is architecturally designed for Snapdragon AI PCs, featuring built-in detection for Qualcomm Oryon CPUs, Adreno GPUs, and Hexagon NPUs.
- **Truthful Hardware Reporting:** In accordance with our Non-Negotiable Rule (*No Fake Hardware Claims*), accelerator status is reported truthfully:
  - If native QNN libraries are compiled: `ACTIVE`
  - If detected but unverified: `DETECTED / NOT VERIFIED` (safe CPU fallback enabled).

---

## 4. Installation

### Option 1: Standard Windows Installer (Recommended)
1. Download `VisionPilot-Setup-0.1.0.exe` from the [release/](file:///c:/Users/rishi/Desktop/Vision%20Pilot/release) folder.
2. Run the installer. It installs cleanly into your local user folder without requiring administrative UAC prompts.
3. Launch **VisionPilot** from the Start Menu.

### Option 2: Portable Distribution
1. Download `VisionPilot-0.1.0-portable.zip` from [release/](file:///c:/Users/rishi/Desktop/Vision%20Pilot/release).
2. Extract to any directory.
3. Run `VisionPilot.exe`. All task history and logs remain self-contained inside the folder.

---

## 5. First Launch Checklist

1. On launch, VisionPilot performs a pre-flight hardware audit and displays your CPU/GPU/NPU status in the footer bar.
2. Test a sample command in the input box:
   ```
   Find the latest PDF in Downloads and move it to my Research folder
   ```
3. VisionPilot will create a structured plan, check safety boundaries, execute the move, independently verify the file's presence in Research, and record the outcome in Task History.

---

## 6. Privacy & Safety Model

- **No Always-On Microphone:** Voice recording operates exclusively via push-to-talk. Audio buffers are processed in-memory and discarded immediately after transcription.
- **No Raw Screenshots Stored:** Visual perception buffers are scrubbed from memory after OCR/UIA analysis; only semantic control metadata is retained.
- **Automatic Secret Redaction:** API keys, bearer tokens, passwords, and sensitive dictionary keys are masked before entering logs or databases.
- **Destructive Deletion Blocked:** Permanent deletion commands (`del /f /q`, `rmdir /s /q`) cannot be approved or bypassed.

---

## 7. AI Runtime & Provider Fallbacks

VisionPilot supports multiple interchangeable reasoning and perception backends:
- **Planning:** Local-First Heuristic Reasoning Engine (`LocalReasoningEngine`) or local SLM.
- **Perception:** Native Windows Media OCR (`Windows.Media.Ocr`) + Win32 UI Automation Core.
- **Voice:** Windows Speech Recognition API or offline quantized Whisper models.
- **Hardware Mode:** Configurable in Settings (`AUTO`, `LOCAL_ONLY`, `CPU_ONLY`, `ACCELERATED_LOCAL_ONLY`).

---

## 8. Building from Source

### Prerequisites
- Python 3.10+ (tested on Python 3.14 Windows 11 ARM64 via Prism)
- PyInstaller 6.x
- Inno Setup 6 (for `.exe` setup installer)

### Build Commands
```powershell
# Run the automated build pipeline
powershell -ExecutionPolicy Bypass -File packaging/scripts/build_windows.ps1

# Verify the generated build
powershell -ExecutionPolicy Bypass -File packaging/scripts/verify_build.ps1
```

Generated outputs will be placed in `release/`:
- `VisionPilot-Setup-0.1.0.exe`
- `VisionPilot-0.1.0-portable.zip`
- `SHA256SUMS.txt`

---

## 9. Testing & Demo Execution

### Automated Flagship Demo
Run the isolated, repeatable flagship demonstration:
```powershell
# Reset demo workspace to known clean state
python scripts/reset_demo_workspace.py

# Execute the complete 6-step flagship workflow through real pipeline
python scripts/run_demo.py
```

### Complete Test Suite
Run all 266 unit, E2E, adversarial security, and benchmark tests:
```powershell
python -m pytest tests/ -v
```

Empirical benchmarks on Qualcomm Snapdragon X Elite:
- **Action Execution Latency:** 0.82 ms (mean)
- **SQLite History Insert:** 4.03 ms (mean)
- **History Query/Search:** 0.88 ms (mean)
- **Task Planning Latency:** ~213 ms (mean)
- **Independent Verification:** ~204 ms (mean)

---

## 10. Troubleshooting

| Issue | Cause | Solution |
|:---|:---|:---|
| **Windows SmartScreen warning** | Release binary is an unsigned open-source build | Click "More info" → "Run anyway". Verify SHA-256 against `release/SHA256SUMS.txt`. |
| **Microphone not responding** | Windows privacy permissions disabled | Enable microphone access in **Windows Settings > Privacy & security > Microphone**. |
| **Action fails with "Path not permitted"** | Target path outside authorized workspace | Add your folder root to `PathSecurityPolicy` in Settings or use default Downloads/Documents directories. |
| **Hardware shows "DETECTED / NOT VERIFIED"** | Native compiled QNN libraries not loaded | Expected on Python Prism emulated runtimes. VisionPilot safely runs CPU/DirectML fallback. |

---

## 11. Known Limitations

- Native Qualcomm Hexagon NPU execution via QNN C-extensions requires a native ARM64 Python build (standard Python 3.14 AMD64 runs under Prism binary translation).
- Multi-monitor setups currently ground actions to the primary active display window.

---

## 12. License
MIT License. Copyright (c) 2026 VisionPilot Project.
