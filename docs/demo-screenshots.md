# VisionPilot — Screenshot & Visual Asset Directory

**Project:** VisionPilot  
**Location:** `assets/screenshots/`  
**Capture Methodology:** Authentic PySide6 widget frame grabs generated via `scripts/capture_real_screenshots.py`.  
**Integrity Notice:** Zero image manipulation, simulated mockups, or fabricated elements. All screenshots represent authentic application states.

---

## 1. Screenshot Catalog

| File Name | UI State / Window | Description |
| :--- | :--- | :--- |
| `01-dashboard.png` | Main Dashboard | Default initial state showing clean branding ("What can I do for you?"), status badge (`● Ready`), command input card with push-to-talk mic button, empty task panel, and hardware telemetry footer (`Snapdragon AI PC • Hexagon NPU: Detected • Runtime: CPU_ONLY`). |
| `02-command.png` | Text Command Input | Populated command editor displaying the flagship multi-step command: *"Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result."* |
| `03-voice.png` | Voice Interaction | Active Push-to-Talk recording state with red pulsing recording indicator and status label displaying listening state. |
| `04-perception.png` | Screen Perception | Active screen perception state fusing Windows UI Automation hierarchy with Windows Media OCR bounding boxes. |
| `05-plan.png` | Task Plan Preview | Structured Task Panel rendering the 4-step execution plan: `FIND_FILE` -> `RENAME_FILE` -> `MOVE_FILE` -> `VERIFY_STATE`. |
| `06-confirmation.png` | Safety Confirmation Modal | Interactive safety confirmation dialog displaying the explicit action (`MOVE_FILE`), target file path (`Research/Qualcomm-AI.pdf`), categorical risk level (`MEDIUM`), and explicit Confirm/Cancel buttons. |
| `07-execution.png` | Action Execution | Active execution progress indicator displaying step-by-step completion in real time. |
| `08-verification.png` | Verification State | Verification Engine actively evaluating ground-truth postconditions (`FileExists` at destination, `FileAbsent` at source). |
| `09-history.png` | Task History Viewer | Full task history dialog (`TaskHistoryDialog`) showing search bar, status filters (`All Statuses`, `COMPLETED`, `FAILED`, etc.), source filters, and recorded execution metrics. |
| `10-runtime.png` | AI Runtime Telemetry | Settings dialog on the **AI Runtime** tab displaying detected hardware (Qualcomm Snapdragon X Elite, Adreno GPU, Hexagon NPU) and active runtime provider. |
| `11-privacy-settings.png`| Privacy Settings Tab | Settings dialog on the **Privacy** tab showing local-only processing toggles, push-to-talk configuration, zero telemetry guarantees, and screenshot non-retention policies. |
| `12-demo-success.png` | Flagship Workflow Success | Verified completion state in MainWindow showing green badge (`● Completed`), activity panel update, and verified destination evidence. |

---

## 2. Privacy & Cleanliness Validation
All captured visual assets have been reviewed to ensure:
- Zero personal documents, photos, or emails visible.
- Zero API keys, passwords, or credentials exposed.
- Zero machine-specific local usernames or private file paths shown.
- Standard 100% DPI light theme aesthetics with deep blue and cyan branding.
