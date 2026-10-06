# VisionPilot — Demonstration Contingency & Fallback Strategy

**Project:** VisionPilot  
**Tagline:** "See. Understand. Act. Verify."  
**Purpose:** Ensure seamless, truthful presentation during live evaluation and judging sessions.

---

## 1. Guiding Principle

**Never fake a result.**  
If an unexpected environment issue arises (e.g. microphone disconnected, display scaling anomaly, or permission conflict), VisionPilot provides deterministic, transparent fallback pathways.

---

## 2. Contingency Scenarios & Procedures

### Scenario A: Microphone or Voice Input Failure
- **Symptom:** Push-to-talk button produces an error banner or fails to capture speech due to missing audio input devices.
- **Immediate Fallback:** Switch immediately to the typed command input editor.
- **Command to Type:**
  ```text
  Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result.
  ```
- **Explanation to Judges:** *"Voice capture uses local push-to-talk audio input. Since microphone hardware is unavailable in this test environment, VisionPilot seamlessly accepts identical natural language input via the text pipeline."*

### Scenario B: NPU Accelerator Verification Status
- **Symptom:** Judge asks why the status bar displays `Hexagon NPU: Detected` but `Runtime: CPU_ONLY`.
- **Truthful Explanation:**
  *"VisionPilot strictly adheres to hardware truthfulness. We distinguish between **Hardware Detected**, **Runtime Available**, and **Active Acceleration**. On this Snapdragon X Elite device running our current packaged evaluation build under Windows ARM Prism emulation, the Hexagon NPU is recognized at the system device layer, but ONNX/QNN runtime bindings are not verified for NPU execution in this process. VisionPilot safely executes on the Snapdragon multi-core CPU with zero crashes."*

### Scenario C: Live Desktop Window Disruption
- **Symptom:** An active window covers the demo directory or alters window focus during perception.
- **Immediate Fallback:** Run the automated headless demo validation script:
  ```powershell
  python scripts/run_demo.py
  ```
- **Explanation to Judges:** *"The flagship workflow can be demonstrated in headless automated mode directly invoking the perception, planner, safety, file executor, and verification engine, logging full structured evidence to the local SQLite database."*

### Scenario D: File Permission or Existing File Collision
- **Symptom:** Target file `Qualcomm-AI.pdf` already exists in `Research/` from a previous demo run.
- **Immediate Fallback:** Execute the deterministic reset script:
  ```powershell
  python scripts/reset_demo_workspace.py
  ```
- **Explanation to Judges:** *"VisionPilot enforces strict anti-collision safety. To guarantee repeatable demonstrations, our isolated demo workspace includes an idempotent reset script that restores three synthetic test PDFs in under 500 milliseconds."*

---

## 3. Real Evidence Fallback (Pre-Recorded & Screenshots)
If a complete live presentation environment failure occurs, evaluators can inspect:
1. **Authentic UI Screenshots:** Located in `assets/screenshots/` (12 high-resolution screenshots capturing every state).
2. **Task History Database:** Viewable directly in the application's **Task History & Audit Trail** viewer (`data/visionpilot.db`).
3. **Automated Test Run:** Run `pytest tests/` (266 passing tests).
