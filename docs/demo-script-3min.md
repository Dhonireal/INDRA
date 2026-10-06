# VisionPilot — 3-Minute Live Demonstration Script

**Total Duration:** 3 Minutes (180 Seconds)  
**Presenter:** Engineering Lead / Founder  
**Application State:** VisionPilot open on desktop, `demo_workspace/` prepared via `scripts/setup_demo_workspace.py`.

---

### [0:00 – 0:25] The Problem & Introduction
*"Hello everyone. We all know modern AI can answer questions, summarize PDFs, and write code. But when you ask an assistant to actually organize your files, manage an application, or complete a multi-step task on your PC, it stops short.*

*Existing desktop automation agents try to click fixed pixel coordinates, break on window resizing, execute dangerous shell commands, or blindly assume an action succeeded without verifying ground truth.*

*This is **VisionPilot** — a privacy-first visual computer-use AI agent built for Windows and Snapdragon AI PCs. Our philosophy is simple: **See. Understand. Act. Verify.**"*

---

### [0:25 – 0:50] Command & Understanding
*(Presenter demonstrates either pressing Push-to-Talk or typing into the Command Editor)*  
*"Let's give VisionPilot a real desktop command:"*

> *"Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result."*

*(Presenter clicks Submit)*  
*"Notice how fast the system responds. In under 25 milliseconds, VisionPilot normalizes the command, extracts intent, and formulates a 4-step structured task plan visible in the Task Panel on the right.*

*Crucially, VisionPilot doesn't guess fixed screen coordinates. It observes system state using Windows UI Automation and on-device Windows Media OCR, resolving files and UI controls semantically."*

---

### [0:50 – 1:20] Safety Gate & User Confirmation
*(Presenter highlights the Task Panel and Safety evaluation)*  
*"Before any computer action takes place, every step passes through our authoritative **ActionSafetyGate**.*

*Notice that VisionPilot assigns categorical risk levels. Safe operations like file inspection are allowed, medium-risk actions like moving files across directories can require explicit confirmation, and dangerous operations like permanent file deletion or shell injection are unconditionally blocked.*

*The agent has **zero** access to arbitrary shell execution or `cmd.exe`. Even if a malicious file name or webpage contains a prompt injection attack, the agent cannot execute unauthorized code."*

---

### [1:20 – 1:55] Action Execution & Ground-Truth Verification
*(Presenter clicks Execute or watches automated execution)*  
*"Now, watch the execution: Step 1 finds the latest PDF by inspection of modification timestamps. Step 2 renames `latest-research.pdf` to `Qualcomm-AI.pdf`. Step 3 moves it into the `Research/` folder.*

*Now look at Step 4: **Independent Verification**.*

*Most agents stop when an operating system call returns. VisionPilot does not. Its independent **VerificationEngine** queries ground truth: it confirms that `Qualcomm-AI.pdf` exists at the destination, and confirms that it is absent from the original Downloads folder.*

*When ground truth matches our postcondition, VisionPilot marks the task **VERIFIED SUCCESS**."*

---

### [1:55 – 2:30] History, Privacy & Snapdragon Runtime
*(Presenter opens the Task History dialog and points to the status bar)*  
*"Every action, plan, verification result, and state transition is immutably logged into our local SQLite task history with automatic privacy redaction of passwords and sensitive tokens.*

*Everything you saw ran local-first. VisionPilot uses push-to-talk microphone capture—no continuous background listening, and no screen streaming to cloud servers.*

*Look at the telemetry footer: VisionPilot is Snapdragon-aware. It detects our Snapdragon X Elite multi-core CPU, Adreno GPU, and Qualcomm Hexagon NPU. While our current packaged evaluation build utilizes verified CPU execution, our runtime provider abstraction is architected to map neural workloads to the NPU as native ARM64 runtimes are deployed."*

---

### [2:30 – 3:00] Closing & Impact
*"In summary, VisionPilot bridges the gap between conversational AI and safe, reliable desktop action. By replacing coordinate guessing with semantic perception, enforcing an authoritative safety gate, and validating results against ground truth, we deliver an assistant you can actually trust.*

**VisionPilot: See. Understand. Act. Verify.**  
*Thank you, and I welcome any questions."*
