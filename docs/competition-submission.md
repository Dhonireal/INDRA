# VisionPilot — Competition Submission Summary

### 1. Project Name
**VisionPilot**

### 2. Tagline & One-Line Pitch
**"See. Understand. Act. Verify."**  
*VisionPilot is a privacy-first visual computer-use AI agent that sees the desktop, understands user intent, safely acts across Windows, and independently verifies the result.*

### 3. The Problem
Traditional conversational AI assistants answer questions and generate text, but cannot safely complete multi-step workflows on a user's computer. When automated assistants do interact with the desktop, they frequently rely on brittle coordinate clicking, lack independent postcondition verification (assuming success simply because an API was called), hallucinate actions, and present severe security and privacy risks by executing arbitrary scripts or streaming private screen content to cloud servers.

### 4. Our Solution
VisionPilot introduces a local-first, closed-loop agent architecture built specifically for modern Windows and Snapdragon AI PCs:
$$\text{Listen} \longrightarrow \text{See} \longrightarrow \text{Understand} \longrightarrow \text{Plan} \longrightarrow \text{Act} \longrightarrow \text{Verify}$$

1. **Push-to-Talk Voice & Text:** Privacy-first voice interaction that captures audio only while held down, with local speech recognition and typed text parity.
2. **Hybrid Screen Perception:** Combines Windows UI Automation (UIA) tree hierarchy with Windows Media OCR for coordinate-free, resolution-independent semantic grounding.
3. **Structured Task Planner:** Formulates strongly typed, validated execution plans with explicit preconditions and postconditions.
4. **Authoritative Safety Gate:** Categorical risk assessment (SAFE to BLOCKED). Permanent file deletion and arbitrary shell scripts are strictly prohibited.
5. **Independent Ground-Truth Verification:** Evaluates postconditions using direct system evidence (e.g. checking filesystem ground truth), preventing false success.
6. **Bounded Recovery:** Deterministic retry, re-perception, or user escalation capped at a strict depth limit.
7. **Local Audit Trail:** Parameterized SQLite task history with automatic privacy redaction.

### 5. Snapdragon AI PC Optimization & Truthfulness
- **Target Platform:** Designed for Snapdragon AI PCs (Qualcomm Snapdragon X Elite / Plus).
- **Hardware-Aware Runtime:** Automatically detects Snapdragon multi-core CPU, Adreno GPU, and Qualcomm Hexagon NPU.
- **Provider Abstraction:** Modular runtime provider architecture supporting DirectML and ONNX Runtime execution providers.
- **Strict Hardware Truthfulness:** VisionPilot truthfully reports when hardware is detected versus when software runtimes are verified. In our current evaluation environment under Windows ARM Prism emulation, the Hexagon NPU is detected as a system entity, while execution safely runs via CPU fallback.

### 6. Demonstrated Flagship Workflow
**User Command:** *"Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result."*  
- Discovers newest PDF based on filesystem timestamp metadata.
- Formulates a 4-step structured plan in under 30ms.
- Clears the ActionSafetyGate for safe file operations.
- Renames the file and verifies existence at the source directory.
- Moves the file to the destination and independently verifies that the destination exists and the source is absent.
- Logs the verified transaction to local SQLite task history.

### 7. Reliability & Testing Evidence
- **Complete Test Suite:** 266 passing tests across unit, integration, adversarial security, and performance benchmarks.
- **Zero Failures:** 100% test pass rate with zero skips.
- **Package Readiness:** Standalone executable, portable ZIP archive, and Inno Setup Windows installer with SHA-256 checksums verified.

### 8. Current Known Limitations
- Hexagon NPU hardware is detected, but active NPU acceleration bindings require native ARM64 QNN execution provider compilation.
- Multi-monitor coordinate fallback is restricted to primary virtual screen coordinates.
- Voice transcription depends on locally installed Windows speech recognition language packs.
