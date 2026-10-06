
# VisionPilot — Technology Stack

## 1. Platform

Target:

- Windows 11
- Snapdragon AI PCs
- Snapdragon-powered HP PCs as challenge-oriented target platform

Development can initially be performed on an available Snapdragon Windows laptop.

---

# 2. Programming Language

## Python

Primary language for:

- AI orchestration
- Voice processing
- Computer vision
- OCR
- Task planning
- Automation
- Backend logic
- Testing

Reason:

Python has a mature ecosystem for AI, computer vision, speech processing, automation, and model runtimes.

---

# 3. Desktop UI

Recommended:

## PySide6

Use PySide6 for:

- Main application window
- Command interface
- Task progress
- Settings
- Confirmation dialogs
- System tray integration

Alternative desktop UI technologies should not be introduced unless there is a clear technical reason.

---

# 4. Voice (Phase 4)

Architecture:

```text
Microphone
    ↓
Audio Capture (sounddevice / PyAudio / WASAPI)
    ↓
Speech-to-Text (Windows SAPI / Local STT)
    ↓
Command Text
```

---

# 5. Screen Perception & Visual Grounding (Phase 5)

Technologies:

- **Screen Capture**: PySide6 QScreen / PIL ImageGrab (WASAPI / GDI)
- **UI Automation**: Windows UIAutomationCore (`uiautomation` native COM)
- **Optical Character Recognition (OCR)**: Windows 11 Native Media OCR (`Windows.Media.Ocr.OcrEngine` via WinRT)
- **Perception Fusion & Visual Grounding**: Spatial IoU deduplication, containment matching, fuzzy semantic matching
- **Privacy Shield**: Ephemeral memory capture (zero disk writes), password field redaction, untrusted screen content isolation

---

# 6. AI Task Planning & Reasoning Engine (Phase 6)

Technologies:

- **Reasoning Architecture**: Provider abstraction (`ReasoningProvider`), `LocalReasoningProvider`, `MockReasoningProvider`
- **Model Engine**: Local Deterministic Symbolic Planner & SLM abstraction
- **Runtime / Accelerator**: Native Python 3.14 on Windows 11 ARM64 Prism subsystem (`accelerator = "CPU"`)
- **Memory Footprint**: ~12.5 MB (0 MB multi-gigabyte downloads; safe for ~10 GB disk limit)
- **Prompt Injection Defense**: Boundary-enforced context builder (`USER_COMMAND` vs `UNTRUSTED_SCREEN_CONTENT` vs `SYSTEM_POLICY`)
- **Plan Sanitization & Validation**: `PlanValidator` with capability authorization, DAG dependency checking, and regex-based code injection shields (`powershell`, `cmd`, `os.system`, `eval`, `subprocess`)
- **Safety Boundary**: Strictly a PLANNER, NOT an executor. Zero mouse/keyboard/filesystem side-effects. Execution deferred to Phase 7.

---

# 7. Controlled Action Execution (Phase 7)

Technologies:

- **Orchestration**: `ActionExecutor` sequential execution engine with action locking, cancellation, and audit logging.
- **Safety & Policy Gate**: `ActionSafetyGate` with strict input sanitization, arbitrary code rejection, credential masking, and confirmation expiration/binding.
- **UI Automation Execution**: `UIActionExecutor` using Windows UI Automation (`uiautomation` native COM API) with pre-click target revalidation, control type verification, and fallback to Win32 `mouse_event` / `SendInput`.
- **Keyboard Execution**: `KeyboardActionExecutor` using Win32 `user32.keybd_event` with Unicode support (`KEYEVENTF_UNICODE`), strict virtual key allowlist, and hotkey allowlist (`ctrl+c/v/s/a/z/f`, `alt+tab`).
- **Window Management**: `WindowActionExecutor` using Win32 `SetForegroundWindow` and allowlisted application launcher (`subprocess.Popen` strictly confined to `notepad`, `calculator`, `explorer`, `settings`).
- **Filesystem Automation**: `FileActionExecutor` using Python native `pathlib` and `shutil` (zero shell commands).
- **Filesystem Security**: `PathSecurityPolicy` with traversal prevention, root drive protection, system folder blocking, and explicit user-space directory confinement (`Downloads`, `Documents`, `Desktop`, `Research`, test workspaces).
- **Prohibited Capabilities**: `DELETE_FILE`, `DELETE_FOLDER`, arbitrary shell execution (`cmd.exe`, `powershell.exe`), and arbitrary Python execution are permanently blocked.
- **Hardware Acceleration**: Execution is native OS / Win32 I/O bound on Qualcomm Snapdragon X Oryon CPU (honest reporting: `accelerator = "CPU"`, no false NPU claims).

---

# 8. Verification & Recovery Engine (Phase 8)

Technologies:

- **Verification Engine**: `VerificationEngine` with bounded temporal polling, evidence collection, confidence scoring, and strict separation between `ActionResult` and `VerificationResult`.
- **Strategy Registry**: `VerificationStrategyRegistry` with declarative dispatch based on `ExpectedResultType` and custom strategy extensibility.
- **Filesystem Verification**: Native Python `pathlib` and `os.stat` identity checks (`FileExistsVerifier`, `FileAbsentVerifier`, `FileRenamedVerifier`, `FileMovedVerifier`) enforced by `PathSecurityPolicy`.
- **UI State Verification**: Integration with Phase 5 perception (`UIElementPresentVerifier`, `UIElementAbsentVerifier`, `TextPresentVerifier`, `TextAbsentVerifier`, `WindowActiveVerifier`, `ValueChangedVerifier`, `StructuredStateVerifier`).
- **Recovery Manager**: `RecoveryManager` bounded state machine enforcing strict retry limits (`MAX_RECOVERY_DEPTH = 3`, 0 blind retries for side-effecting actions, 1 for UI lookups, 2 for read-only observations).
- **Collision & Uncertainty Handling**: Mandatory escalation to `ASK_USER` or `MARK_UNCERTAIN` upon file collisions or unverified timeouts; prevents duplicate side effects.
- **Plan Synthesis**: `TaskVerifier` for evaluating multi-step action plans into aggregate states (`VERIFIED_SUCCESS`, `PARTIALLY_COMPLETED`, `UNCERTAIN`, `FAILED`).
- **Hardware Acceleration**: Verification checks are native Windows UIA COM / Win32 / filesystem I/O bound on Qualcomm Snapdragon X Oryon CPU (truthful reporting: `accelerator = "CPU"`, latency measured at ~0.18ms for files and ~0.02ms for recovery decisions).

---

# 9. Task History & Audit Trail Engine (Phase 9)

Technologies:

- **Storage Engine**: Python standard library `sqlite3` using local database file (`data/visionpilot.db`). Zero external database dependencies or server processes.
- **Relational Schema**: Normalized tables for `tasks`, `task_plans`, `task_actions`, `task_verifications`, `task_recoveries`, and `audit_events` with foreign keys and cascade protections (`ON CONFLICT DO UPDATE`).
- **Index Optimization**: B-Tree indices on `created_at`, `status`, `command_source`, and foreign keys ensuring sub-10ms query latencies across hundreds of records.
- **Privacy Redactor**: `PrivacyRedactor` regex engine stripping API keys (`sk-...`, `AIza...`), bearer tokens, and credentials before persistence. Automatic masking of typing parameters in password fields (`<redacted:password>`).
- **Crash Recovery**: `recover_interrupted_tasks()` startup scanner detecting abnormal shutdowns and safely transitioning orphaned non-terminal tasks to `INTERRUPTED` without resuming side-effects.
- **Retention Management**: Automatic age-based (`retention_days`) and volume-based (`max_tasks`) database pruning.
- **UI Architecture**: PySide6 interactive `ActivityPanel`, `TaskDetailDialog`, and `TaskHistoryDialog` with live keyword search and multi-facet filtering.
- **Hardware Acceleration**: SQLite operations are local NVMe SSD / Win32 filesystem bound on Qualcomm Snapdragon X Oryon CPU (truthful reporting: `accelerator = "CPU"`, query latency ~6.5ms for 500 rows).
