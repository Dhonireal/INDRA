# VisionPilot — Judge Q&A Technical Reference

**Project:** VisionPilot  
**Tagline:** "See. Understand. Act. Verify."  
**Purpose:** Precise, technically truthful responses to anticipated evaluation and judging questions.

---

### Q1. How is VisionPilot different from Copilot or ChatGPT?
**Answer:**  
Copilot and ChatGPT are conversational models designed to generate text and code answers. VisionPilot is an autonomous computer-use agent that directly interacts with the Windows operating system through a closed loop: **See -> Understand -> Plan -> Act -> Verify**. VisionPilot observes the desktop semantically, formulates structured execution plans, enforces a safety gate, executes native actions, and independently verifies that the real-world ground truth was achieved.

---

### Q2. How does VisionPilot understand the screen without using fragile coordinates?
**Answer:**  
VisionPilot uses a hybrid perception hierarchy:
1. **Windows UI Automation (UIA):** Queries native accessibility trees to extract control roles, bounding rectangles, and accessible names.
2. **Windows Media OCR:** On-device optical character recognition that localizes text elements when controls are unexposed via UIA.
3. **Semantic Grounding:** Binds action intents to control names and roles rather than static pixel coordinates, ensuring resilience against window movement, resolution changes, and display scaling. Coordinates are strictly an emergency fallback.

---

### Q3. How does VisionPilot avoid taking dangerous or destructive actions?
**Answer:**  
Through our multi-tier safety architecture:
1. **ActionSafetyGate:** Categorizes actions from `SAFE` to `BLOCKED`.
2. **Blocked Capabilities:** Permanent deletion (`DELETE_FILE`, `rmdir`, `del`), arbitrary shell execution (`powershell`, `cmd.exe`), and registry manipulation are hardcoded as `BLOCKED`.
3. **PathSecurityPolicy:** Canonical path resolution blocks directory traversal (`../`) and prevents operations outside user-permitted roots (`Downloads`, `Documents`, `Desktop`, `Research`).
4. **Interactive Confirmation:** Medium and high-risk actions prompt the user with explicit dialogs bound cryptographically/logically to the specific task and action parameters.

---

### Q4. What happens if perception is wrong or an element moves?
**Answer:**  
VisionPilot incorporates a bounded **Recovery Engine**:
1. If an expected target element is not found, the agent triggers an on-demand re-perception pass to re-read the screen.
2. If the state still cannot be reconciled, the planner attempts a re-plan or escalates to the user.
3. Recovery depth is strictly bounded (maximum 3 attempts) to prevent infinite loops, and recovery operations can never bypass safety or verification gates.

---

### Q5. How does independent verification work? Why is it necessary?
**Answer:**  
Conventional automation assumes an action succeeded if the operating system API returned status code 0. This creates false success when operations fail silently or race conditions occur.  
VisionPilot's `VerificationEngine` queries real system evidence:
- For file moves: It asserts that the file exists at the destination *and* is absent from the source.
- For UI actions: It polls the accessibility tree to confirm property changes or window focus shifts.  
A task is only marked `COMPLETED` when verification passes.

---

### Q6. Why is VisionPilot built for Snapdragon AI PCs?
**Answer:**  
Snapdragon AI PCs provide high-efficiency neural and multi-core processing designed for continuous client-side AI. Desktop computer use requires low latency and high privacy: streaming screen captures or continuous audio to the cloud creates bandwidth bottlenecks, privacy liabilities, and high operational costs. Snapdragon's architecture enables local-first perception, on-device OCR, and responsive planning directly on the edge device.

---

### Q7. Is everything running locally?
**Answer:**  
Yes. All core capabilities demonstrated in VisionPilot run local-first on the user's PC:
- Screen capture: Local Windows Desktop Duplication / Win32 GDI.
- OCR: Local Windows Media OCR engine (`WinRT`).
- Speech recognition: Local Windows speech recognition.
- Execution & Verification: Local Python `pathlib` and Windows accessibility APIs.
- Storage: Local encrypted/parameterized SQLite database.
No screen images, commands, or audio are transmitted to external cloud servers.

---

### Q8. Is the Qualcomm Hexagon NPU actually being used right now?
**Answer:**  
*We believe in complete technical truthfulness.* In our current packaged build running on this Snapdragon X Elite device under Windows 11 ARM64 Prism emulation, the Hexagon NPU is **detected** at the hardware level, but active execution is running via our **verified CPU fallback provider**. Compiling native ARM64 QNN execution bindings is our immediate roadmap milestone for direct NPU offloading. We never claim NPU execution where it has not been directly verified.

---

### Q9. What happens if hardware acceleration is unavailable?
**Answer:**  
VisionPilot's runtime provider abstraction provides automated, graceful fallback. If the NPU or DirectML GPU provider is unavailable or unverified, the system transparently executes on the Snapdragon multi-core CPU. The application never crashes due to missing accelerators and truthfully displays `Runtime: CPU_ONLY` in the status telemetry.

---

### Q10. How do you prevent prompt injection from untrusted screen content or web pages?
**Answer:**  
VisionPilot treats all screen text, OCR output, and user text as untrusted data:
1. Input text is validated against strict length limits and stripped of shell metacharacters.
2. The AI Task Planner has a closed capability schema and cannot invent new action types.
3. `PlanValidator` and `ActionSafetyGate` enforce regex filters blocking shell execution tokens (`powershell`, `cmd.exe`, `subprocess`, `os.system`, `eval`).
4. Even if an untrusted web page says *"Delete all files"*, the planner rejects the capability, and the filesystem executor unconditionally blocks deletion.

---

### Q11. Can the agent execute arbitrary scripts or shell commands?
**Answer:**  
**No.** VisionPilot does not expose shell or command-line execution capabilities to the planner. File actions use standard Python `pathlib` APIs. Window actions use `subprocess.Popen` with fixed argument arrays (`shell=False`) restricted to whitelisted binary executables (e.g. `notepad.exe`). Arbitrary code execution is strictly prohibited by architectural design.

---

### Q12. How are passwords and sensitive credentials handled?
**Answer:**  
1. Perception: UIA inspects `IsPassword` accessibility attributes and suppresses reading text from masked password fields.
2. Storage: The `PrivacyRedactor` scrubs passwords, API keys, tokens, and authorization headers before records are committed to the SQLite database.
3. UI: Sensitive values are displayed with mask characters (`••••••••`).

---

### Q13. How is user privacy protected regarding audio and screen data?
**Answer:**  
1. **Push-to-Talk Only:** The microphone captures audio only while the user explicitly holds down the recording trigger; there is no always-on listening.
2. **Zero Audio Retention:** Audio buffers are processed in memory and discarded immediately upon transcription.
3. **On-Demand Perception:** The screen is inspected only when an active command requires grounding; there is no background surveillance or screen recording.
4. **Local Audit Trail:** All task history stays strictly on the user's machine in `%LOCALAPPDATA%\VisionPilot\data\`.

---

### Q14. What happens when an action fails?
**Answer:**  
When an action fails:
1. The error code and evidence are captured.
2. The `RecoveryManager` evaluates whether the failure is recoverable (e.g. re-trying with updated perception).
3. If unrecoverable or if the retry limit is exceeded, VisionPilot aborts safely, preserves the current state without side effects, notifies the user via an in-app error banner, and logs the full diagnostic event to SQLite. The app never crashes.

---

### Q15. How scalable is the architecture?
**Answer:**  
VisionPilot is built on a clean event-driven architecture (`EventBus`), dependency injection, and modular domain layers. Adding a new capability requires only implementing the typed capability interface and registering it with the `CapabilityRegistry`. New verification strategies and AI runtime providers can be plugged in without modifying core orchestration logic.

---

### Q16. How is VisionPilot packaged and distributed?
**Answer:**  
VisionPilot is packaged for Windows 11 as:
1. **Windows Installer (`VisionPilot-Setup-0.1.0.exe`):** Built with Inno Setup for standard enterprise/consumer deployment, desktop shortcuts, and clean uninstallation.
2. **Standalone Portable ZIP (`VisionPilot-0.1.0-portable.zip`):** Self-contained directory requiring zero installation.
Both packages bundle all dependencies and assets, verify SHA-256 checksums, and store user data in `%LOCALAPPDATA%\VisionPilot`.

---

### Q17. What are the current limitations of VisionPilot?
**Answer:**  
1. **NPU Runtimes:** Currently running via verified CPU provider under Prism emulation; native ARM64 compilation for direct Hexagon NPU offloading is in development.
2. **Multi-Monitor Coordinate Fallback:** Primary monitor coordinates are prioritized during coordinate-based fallback.
3. **Language Packs:** Local voice transcription requires the relevant Windows speech recognition language pack to be installed on the host system.
