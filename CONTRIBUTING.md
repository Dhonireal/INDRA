# Contributing to VisionPilot

Thank you for your interest in contributing to **VisionPilot: Privacy-First Visual Computer-Use AI Agent**.

---

## 1. Absolute Architecture & Safety Principles

All contributors must adhere strictly to VisionPilot's core safety and architectural contracts:

1. **Never Introduce Arbitrary Shell or Code Execution**:
   - The agent MUST NEVER execute arbitrary PowerShell, `cmd.exe`, `subprocess` with `shell=True`, or Python `eval()`/`exec()`.
   - File actions must use native Python `pathlib` and `shutil` within authorized directories.
2. **Preserve the Core Loop**:
   $$\text{Listen} \longrightarrow \text{See} \longrightarrow \text{Understand} \longrightarrow \text{Plan} \longrightarrow \text{Act} \longrightarrow \text{Verify}$$
   - Never skip the `ActionSafetyGate`.
   - Never skip the `VerificationEngine` (never assume success merely because an OS API call returned 0).
3. **Hardware Truthfulness**:
   - Never label a CPU fallback result as an NPU or accelerator result.
   - Distinguish between **Hardware Detected**, **Runtime Available**, and **Active Acceleration**.
4. **Coordinate-Free Perception**:
   - Always prioritize Windows UI Automation (UIA) and OCR over raw screen coordinates. Screen coordinates are strictly a last-resort fallback.

---

## 2. Development Setup

### Prerequisites
- Windows 11 (x86_64 or ARM64)
- Python 3.11+
- Virtual environment (`.venv`)

### Installation
```powershell
# Clone or navigate to the repository
cd "Vision Pilot"

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install runtime and testing dependencies
pip install -r requirements.txt
```

---

## 3. Running Tests & Demo

```powershell
# Run the complete test suite
pytest tests/

# Run the isolated flagship demo runner
python scripts/run_demo.py

# Reset the demo workspace
python scripts/reset_demo_workspace.py
```

---

## 4. Packaging

```powershell
# Run packaging script (requires PyInstaller and Inno Setup 6)
powershell -ExecutionPolicy Bypass -File packaging/scripts/build_windows.ps1
```

---

## 5. Security & Privacy Guidelines
- Parameterize all SQL queries (`?` placeholders).
- Sanitize and redact passwords, tokens, and authorization headers using `PrivacyRedactor`.
- Verify path safety using `PathSecurityPolicy` before opening or modifying files.
