# Production EXE Debug Report

**Project:** VisionPilot — Privacy-First Visual Computer-Use AI Agent  
**Date:** October 3, 2026  
**Auditor:** Principal Software Engineer, QA Lead, & Demo Reliability Engineer  
**Status:** ROOT-CAUSE DIAGNOSIS COMPLETE (NO CODE MODIFICATIONS APPLIED)  

---

## 1. Environment
- **Operating System:** Windows 11 Home / Pro (ARM64, Build 26100)
- **CPU Architecture:** ARM64 (Snapdragon X Elite 12-Core, running AMD64 binary translation via Windows 11 Prism)
- **Detected Hardware:**
  - CPU: Qualcomm Snapdragon X Elite
  - GPU: Qualcomm Adreno X1-45 GPU
  - NPU: Qualcomm Hexagon NPU (Detected via Windows PnP)
- **Installed VisionPilot Version:** 0.1.0

---

## 2. Executable & Deployment
- **Packaged Executable Path:** `C:\Users\rishi\AppData\Local\Programs\VisionPilot\VisionPilot.exe` (Installed) and `c:\Users\rishi\Desktop\Vision Pilot\dist\VisionPilot\VisionPilot.exe` (Distribution build)
- **Installer Version:** `VisionPilot-Setup-0.1.0.exe` (Inno Setup 6.4.4)
- **Build Method:** PyInstaller 6.12.0 one-folder distribution with `--noconsole` and custom specification (`packaging/pyinstaller/VisionPilot.spec`).

---

## 3. Reproduction & User Observations

When the installed executable is launched as a real user:
1. The desktop GUI opens cleanly, displaying the header, command input editor, task panel, and hardware telemetry footer.
2. When a command is submitted (e.g. `"Find the latest PDF in Downloads..."` or `"open youtube"`):
   - The UI displays a card in Recent Activity ("PLANNING", then "READY").
   - A structured plan preview is shown inside the Task Panel.
   - **Crucial Observation:** The application does **not** proceed to execute the plan automatically. It sits waiting for the user to find and click a secondary "Execute Plan" button inside the preview card.
3. If the user clicks "Cancel" (thinking the agent hung):
   - Cancellation is processed.
   - However, for every subsequent command typed into the app, the agent immediately fails with:
     `TaskPlanner already cancelled before planning command`
   - The application becomes completely unresponsive to further commands.
4. If the user clicks "Execute Plan" on the flagship file workflow:
   - Step 1 (`FIND_FILE`) succeeds in finding the latest PDF.
   - Step 2 (`RENAME_FILE`) immediately fails with `FileNotFoundError` because it looks for a file named `"selected_file"`, having never received the actual file path identified in Step 1.
5. If the user clicks the microphone button and speaks:
   - Audio is recorded, but transcription fails 100% of the time with:
     `Voice transcription failed: Could not understand the spoken words. Please speak clearly.`
6. If the user executes any task a second time:
   - Verification fails with `Task failed (2/1 steps verified)` because prior verification records leak across task executions.

---

## 4. Feature Test Results

| Feature | Action Tested | Expected Outcome | Actual Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **A. Startup** | Launch `VisionPilot.exe` | Boots in <2s, connects to SQLite, shows UI | Boots cleanly in 1.8s, telemetry footer accurate | **WORKING** |
| **B. Text Command Input** | Enter command & press Enter | Validates, normalizes, plans, and acts | Normalizes and plans, but stops at preview card without executing | **BROKEN UX** |
| **C. Voice / Microphone** | Push-to-talk speech input | Records audio and transcribes spoken text | Records audio, but `LocalSTTProvider` always raises `VoiceError` | **BROKEN** |
| **D. Screen Capture** | On-demand screen capture | Captures desktop frame | GDI/Win32 capture succeeds | **WORKING** |
| **E. UI Automation** | UIA tree extraction | Enumerates active window controls | Extracted 115 controls in 0.98s | **WORKING** |
| **F. OCR** | Windows Media OCR | Optical character recognition | WinRT OCR initializes with `en-GB`, ready | **WORKING** |
| **G. Task Planner** | Formulate multi-step plan | Generates validated `PlanStep` sequence | Plans successfully, but permanently freezes if cancelled once | **BROKEN (Sticky Cancel)** |
| **H. Safety Engine** | Evaluate action risk | Categorizes action risk (SAFE to BLOCKED) | Path policy and risk evaluation work properly | **WORKING** |
| **I. Confirmation Dialog** | User confirmation on Medium/High risk | Modal dialog displayed | Dialog displays correctly with Confirm/Cancel | **WORKING** |
| **J. File Operations** | Execute `FIND_FILE` -> `RENAME_FILE` | Discovers latest PDF, renames and moves it | Fails at Step 2 because parameter is statically `"selected_file"` | **BROKEN (Step Binding)** |
| **K. Verification** | Independent postcondition check | Verifies ground truth against actual files | Verifies Step 1, but fails subsequent tasks due to state accumulation | **BROKEN (State Leak)** |
| **L. Recovery** | Bounded recovery on failure | Re-tries or escalates to user | Evaluates recovery policy properly | **WORKING** |
| **M. Task History** | Persist task records to SQLite | History saved in `%LOCALAPPDATA%\VisionPilot` | Writes properly to SQLite; shows failed tasks | **WORKING** |
| **N. Settings** | View/modify preferences | Settings saved, history cleared | Dialog works; Clear History succeeds | **WORKING** |
| **O. Runtime Detection** | Audit hardware | Detects Snapdragon X Elite, GPU, NPU | WMI queries succeed, truthful reporting | **WORKING** |

---

## 5. Production Error Logs

Direct excerpts from `%LOCALAPPDATA%\VisionPilot\logs\visionpilot.log`:

### Log Excerpt 1: Sticky Cancellation Disabling Planner
```text
2026-10-03 15:13:48 [INFO] [VisionPilot] Cancel requested for task: task_bcfc6ac0b92f
2026-10-03 15:13:48 [INFO] [VisionPilot] MainWindow cancelling task: task_bcfc6ac0b92f
2026-10-03 15:13:48 [INFO] [VisionPilot] TaskPlanner cancellation requested.
2026-10-03 15:13:48 [INFO] [VisionPilot] ActionExecutor cancellation requested.
...
2026-10-03 15:14:02 [INFO] [VisionPilot] Command text submitted via UI
2026-10-03 15:14:02 [INFO] [VisionPilot] MainWindow delegating command to CommandService: open youtube
2026-10-03 15:14:02 [INFO] [VisionPilot] TaskPlanner already cancelled before planning command [cmd_059dec388400]
```

### Log Excerpt 2: Voice Recognition Inability
```text
2026-10-03 15:13:17 [INFO] [VisionPilot] Audio recording started on 'Microphone Array (Qualcomm(R) Aqstic(TM) ACX Static Endpoints Audio Device)' (Max: 15s)
2026-10-03 15:13:20 [INFO] [VisionPilot] Stopping voice recording...
2026-10-03 15:13:20 [INFO] [VisionPilot] Audio recording stopped. Captured 60098 bytes PCM.
2026-10-03 15:13:20 [INFO] [VisionPilot] Local STT provider initialized successfully.
2026-10-03 15:13:20 [WARNING] [VisionPilot] Voice transcription failed: Could not understand the spoken words. Please speak clearly. | Details: Speech was unintelligible.
```

### Log Excerpt 3: Verification Leaking Prior Task Results
```text
2026-10-03 15:13:14 [INFO] [VisionPilot] Verification [ver_593a706946] for action [act_cacca26d8f]: status=VERIFIED, verified=True, confidence=1.00 (StructuredStateVerifier)
2026-10-03 15:13:14 [INFO] [VisionPilot] Task Plan [plan_7cb8405eb63f] Final Verification: FAILED - Task failed (2/1 steps verified).
2026-10-03 15:13:14 [ERROR] [VisionPilot] Plan [plan_7cb8405eb63f] failed verification: Task failed (2/1 steps verified).
```

---

## 6. Root Cause Analysis

### Root Cause 1 (P0): Sticky Cancellation State
- **Location:** `app/agent/task_planner.py` (lines 81–84, 200–205) and `app/execution/action_executor.py` (lines 91–94, 318–322).
- **Mechanism:** Calling `cancel()` sets `self._is_cancelled = True`. Neither `TaskPlanner.create_plan()` nor `ActionExecutor.execute_plan()` resets `self._is_cancelled = False` at the start of a new task.
- **Impact:** Once any task is cancelled (or the user clicks cancel), all subsequent commands in that application session are permanently rejected.

### Root Cause 2 (P0): Missing Step-to-Step Parameter Forwarding in Planner/Executor
- **Location:** `app/agent/providers/local_reasoning.py` (lines 343–357) and `app/execution/action_executor.py`.
- **Mechanism:** In `_plan_file_workflow`, Step 1 (`FIND_FILE`) identifies the latest PDF. However, Step 2 (`RENAME_FILE`) statically specifies `target.name = "selected_file"` without referencing Step 1's output. When executed, `FileActionExecutor` attempts to resolve `selected_file`, which does not exist, causing Step 2 to fail immediately.
- **Impact:** Multi-step file management workflows cannot execute through the real application pipeline.

### Root Cause 3 (P1): Verification State Leak Across Task Runs
- **Location:** `app/execution/action_executor.py` (lines 83, 203).
- **Mechanism:** `self.step_verifications: List = []` is initialized once in `__init__`. In `execute_plan()`, step verifications are appended without clearing the list at the beginning of the plan.
- **Impact:** On any second or subsequent task execution, `TaskVerifier.evaluate_task_plan()` receives historical step verifications from prior tasks. It compares `verified_steps` against `total_steps` of the current plan. Because `verified_steps > total_steps`, the task is falsely marked as `FAILED`.

### Root Cause 4 (P1): Stubbed Local Speech-to-Text Implementation
- **Location:** `app/voice/providers/local_stt.py` (lines 101–147).
- **Mechanism:** `LocalSTTProvider` attempts `recognize_sphinx` (which is not installed in the distribution) and falls back to `_recognize_via_sapi()`, which is an incomplete stub that hardcoded returns `None`.
- **Impact:** Voice recording always fails with "Speech was unintelligible", rendering voice input non-functional.

### Root Cause 5 (P1): Two-Phase UI Orchestration Without Auto-Execution
- **Location:** `app/ui/main_window.py` (lines 282–322).
- **Mechanism:** `_handle_command_submitted` only creates and displays the plan preview; it does not invoke `_handle_execute_plan()`. The user must manually find and click the secondary "Execute Plan" button inside the preview card.
- **Impact:** Users typing a command (e.g. "Find latest PDF...") see the agent plan the task and then stop completely, giving the impression that the software is frozen or non-functional.

---

## 7. Severity & Classification

| Issue | Severity | Category | Description |
| :--- | :--- | :--- | :--- |
| **Sticky Cancellation Flag** | **P0 (Critical)** | RUNTIME LOGIC | Permanently disables planner & executor after any cancellation. |
| **Missing Step Output Chaining** | **P0 (Critical)** | PLANNER / EXECUTOR | Step 2 cannot resolve Step 1 file output (`selected_file`). |
| **Verification State Accumulation** | **P1 (Major)** | VERIFICATION | Subsequent task runs fail verification due to leftover verification records. |
| **Local STT Provider Stub** | **P1 (Major)** | VOICE PROVIDER | Push-to-talk voice input fails 100% of the time. |
| **Manual Execution Requirement** | **P1 (Major)** | UI ORCHESTRATION | Commands stop at planning phase without executing unless secondary button clicked. |

---

## 8. Recommended Fix (Awaiting Instructions)

1. **Reset Cancellation State on New Invocation:**
   - In `TaskPlanner.create_plan()`: add `self._is_cancelled = False` at the start of plan generation.
   - In `ActionExecutor.execute_plan()`: add `self._is_cancelled = False` at the start of plan execution.
2. **Clear Executor History Per Plan:**
   - In `ActionExecutor.execute_plan()`: reset `self.step_verifications = []`, `self._completed_action_ids = set()`, and `self._execution_history = []` at the beginning of each plan.
3. **Implement Dynamic Step Output Binding:**
   - When Step 1 (`FIND_FILE`) produces `evidence["found_path"]`, `ActionExecutor` should substitute this path into dependent downstream steps (`RENAME_FILE`, `MOVE_FILE`) where `target.name in ("selected_file", "latest.pdf")` or `parameters["source_path"]` is missing.
4. **Wire Native Windows Speech Recognition / Fallback in STT:**
   - Complete the native Windows Speech API (SAPI) or Windows.Media.SpeechRecognition binding in `app/voice/providers/local_stt.py` to return transcribed text, or provide a reliable local fallback.
5. **Add Configurable Auto-Execution Option:**
   - In `MainWindow._handle_command_submitted()`, if auto-execution is enabled (or for low-risk plans), automatically trigger `_handle_execute_plan()` so the agent seamlessly performs the full loop: Understand -> Plan -> Act -> Verify.

---

## 9. Files That Require Modification (For Future Task)
- `app/agent/task_planner.py` (reset cancellation flag)
- `app/execution/action_executor.py` (reset cancellation flag, clear step verifications, forward step outputs)
- `app/voice/providers/local_stt.py` (fix native Windows speech transcription)
- `app/ui/main_window.py` (auto-execute ready plans or provide clear progress feedback)

## 10. Files That Should NOT Be Modified
- `packaging/pyinstaller/VisionPilot.spec` (packaging configuration and hiddenimports are sound)
- `app/storage/database.py` (SQLite schema and migrations are healthy)
- `app/storage/repositories.py` (repositories function correctly)
- `app/execution/safety_gate.py` (safety gate correctly enforces risk policies)
- `app/hardware/device_detector.py` (hardware detection is accurate and truthful)
