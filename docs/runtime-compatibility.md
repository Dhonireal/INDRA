# VisionPilot — AI Runtime Compatibility Matrix

> Document: Runtime Compatibility Analysis  
> Platform: Windows 11 on Snapdragon X (Lenovo 83N3)  
> Environment: Python 3.14 (AMD64 on WoA Prism) & Native Windows 11 ARM64 APIs  

---

## 1. Executive Summary

This document outlines the verified and feasible AI runtimes, perception engines, speech-to-text backends, and reasoning providers for VisionPilot on this specific Snapdragon X machine.

Per **Non-Negotiable Rule 3** (*No Fake Snapdragon Claims*) and **Section 43** (*When Hardware Acceleration is Not Available*), VisionPilot strictly reports actual acceleration status and falls back gracefully to GPU (DirectML) or optimized CPU execution when a dedicated NPU backend is not compiled or loaded.

---

## 2. Hardware Capabilities & Acceleration Tiers

```
┌─────────────────────────────────────────────────────────────┐
│                      SNAPDRAGON X PC                        │
├──────────────────────────────┬──────────────────────────────┤
│ Oryon CPU (8 Cores)          │ Adreno X1-45 GPU             │
│ • Highly efficient FP32/INT8 │ • DirectML execution         │
│ • Always available fallback  │ • Direct3D 12 acceleration   │
├──────────────────────────────┴──────────────────────────────┤
│ Hexagon NPU (ComputeAccelerator Class, Driver oem48.inf)     │
│ • Hardware is Started & Operational in Windows Device Manager│
│ • Requires QNN Execution Provider or DirectML NPU operator   │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Runtime Analysis

### 3.1 Windows UI Automation & Win32 Native Layer
- **Status**: **Fully Supported & Operational**
- **Libraries**: `pywin32`, native Windows COM / UI Automation APIs (`UIAutomationCore.dll`)
- **Use Case**: Primary screen grounding strategy (Section 6, Rule 4: *No Hardcoded Coordinates as Primary Strategy*).
- **Performance**: Zero inference overhead, instant sub-millisecond element tree resolution, deterministic button/input/window bounding coordinates.

### 3.2 Optical Character Recognition (OCR) Runtimes
1. **Windows Native OCR (`Windows.Media.Ocr`)**:
   - **Status**: **Usable via WinRT / Ctypes**
   - **Hardware Acceleration**: Built into Windows 11; uses hardware acceleration where available, runs completely offline, language packs pre-installed.
   - **Zero External Binary Requirement**: Eliminates Tesseract executable dependency.
2. **OpenCV (`opencv-python 5.0.0.93`)**:
   - **Status**: **Installed & Verified**
   - **Use Case**: Image preprocessing, cropping, template matching, bounding box calculations.
3. **Tesseract / Fallback OCR**:
   - **Status**: Requires external tesseract binary; secondary fallback if WinRT OCR is unavailable.

### 3.3 Speech-to-Text (STT) Runtimes
1. **Windows Native Speech Recognition / SAPI**:
   - **Status**: **Native Windows 11 API**
   - **Hardware Acceleration**: Leverages Windows audio subsystem; offline recognition profiles supported.
2. **Local Whisper / ONNX STT**:
   - **Status**: Compatible via ONNX Runtime (DirectML / CPU).
   - **Models**: `whisper-tiny` / `whisper-base` quantized to INT8 or FP16.
   - **Storage Impact**: ~40–150 MB (safe for the 10 GB disk headroom).
3. **Provider Architecture (`STTProvider`)**:
   - Abstract interface allowing:
     - `LocalSTTProvider` (Offline Windows Native / ONNX)
     - `MockSTTProvider` (Deterministic testing for automated test suites)
     - `OptionalFallbackProvider` (Configurable remote endpoint if chosen by user)

### 3.4 AI Reasoning & Task Planning Runtimes
1. **Rule-Based & Semantic Command Understanding**:
   - **Status**: **Local, Deterministic & Zero Latency**
   - **Use Case**: Structured parsing of high-frequency computer-use commands (file management, browser navigation, window switching, application launches).
2. **Local Small Language Models (SLM) via ONNX Runtime / DirectML**:
   - **Status**: Feasible with 1B–3B parameter quantized models (e.g. Phi-3-mini INT4, SmolLM) via DirectML on Qualcomm Adreno GPU.
   - **Disk Consideration**: Requires ~1.5–2.0 GB disk space; user configuration can enable local model downloads when sufficient disk space is confirmed.
3. **Multimodal API / Fallback Provider**:
   - **Status**: Optional developer API endpoint (e.g., Gemini, OpenAI, Claude, or local Ollama server if running).
   - **Design Rule**: Must be decoupled behind `ReasoningProvider` interface so VisionPilot functions end-to-end locally with deterministic planning and structured schema output.

### 3.5 Qualcomm QNN & ONNX Runtime DirectML
- **ONNX Runtime (`onnxruntime` / `onnxruntime-directml`)**:
  - DirectML provider utilizes the Qualcomm Adreno X1-45 GPU out of the box on Windows 11.
  - Qualcomm Hexagon NPU is targeted either via QNN execution provider (`onnxruntime-qnn`) or Windows Copilot+ runtime bindings.
  - VisionPilot's `DeviceDetector` inspects runtime device initialization at boot and flags the exact execution provider (`NPU`, `DirectML_GPU`, or `CPU`).

---

## 4. Architectural Decision Summary

| Component | Selected Primary Implementation | Fallback Implementation |
| :--- | :--- | :--- |
| **Desktop UI** | PySide6 (Qt6) | Headless / CLI Test Harness |
| **Perception (UI Tree)** | Windows UI Automation (`pywin32` / COM) | OCR / Vision Grounding |
| **Perception (OCR)** | Native Windows Media OCR / OpenCV | Pre-processed bounding box engine |
| **Input / Voice** | System Audio Capture + STT Provider | Direct Text Command Pipeline |
| **Action Execution** | Native Windows APIs / Win32 Automation | Controlled Win32 SendInput |
| **Safety Engine** | Strict 4-tier Policy (`SAFE`, `LOW`, `MEDIUM`, `HIGH`) | Interactive Qt Dialog Confirmation |
| **Persistence** | SQLite3 (`tasks.db`) | In-memory Task Repository |

---

## 5. Non-Negotiable Compliance Confirmation

- [x] **No Fake NPU claims**: Indicator explicitly reports `Adreno GPU (DirectML)`, `CPU`, or `Hexagon NPU` based on actual runtime session creation.
- [x] **No Hardcoded Coordinates**: Action targets are resolved via UI Automation elements and OCR bounding boxes.
- [x] **No Credential Access**: Strictly sandboxed from browser passwords, Windows Credential Manager, and secret stores.
- [x] **Fail-Safe Recovery**: Retry threshold capped at 3 attempts; user intervention requested on ambiguity.

---

## 6. Phase 11 Empirical Runtime Validation Findings

Validated during Phase 11 execution:
1. **Device Detection & Enumeration:**
   - Qualcomm Snapdragon X Elite, Qualcomm Adreno GPU, and Qualcomm Hexagon NPU successfully detected via Windows SetupAPI, WMI, and driver metadata.
2. **Truthfulness Invariant Enforcement:**
   - In the test environment (Python 3.14 AMD64 running under Windows on ARM Prism Emulation), native QNN/DirectML C-extension acceleration libraries are unavailable.
   - Per Rule 3, status is recorded as **DETECTED / NOT VERIFIED** and active execution provider defaults safely to `CPU_ONLY` (`LocalReasoningEngine`).
   - 13 hardware runtime tests in `tests/unit/test_runtime_benchmarks.py` verified that CPU results are never falsely labeled as NPU, latency values remain positive and non-fabricated, and runtime state transitions are truthful.

