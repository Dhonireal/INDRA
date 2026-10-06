# VisionPilot — Environment Report

> Audit Date: October 2026 (Verified via System & Hardware Probes)  
> Host System: Lenovo 83N3 (ARM64-based PC)  
> Environment Validation: Phase 0 Hardware & Runtime Audit  

---

## 1. Operating System & Platform

| Attribute | Detected Value | Notes |
| :--- | :--- | :--- |
| **Operating System** | Microsoft Windows 11 Home Single Language | Verified via `Win32_OperatingSystem` |
| **OS Version** | 10.0.26200 | Build 26200 |
| **OS Architecture** | 64-bit ARM Processor (`ARM64`) | Windows on ARM (WoA) native kernel |
| **System Manufacturer** | LENOVO | Verified via `Win32_ComputerSystem` |
| **System Model** | 83N3 | Snapdragon X-powered laptop |
| **System Type** | ARM64-based PC | Native ARM64 platform |

---

## 2. Processor (CPU)

| Attribute | Detected Value |
| :--- | :--- |
| **Processor Name** | Snapdragon(R) X - X126100 - Qualcomm(R) Oryon(TM) CPU |
| **Manufacturer** | Qualcomm Technologies Inc. |
| **Cores / Threads** | 8 Physical Cores / 8 Logical Processors |
| **Architecture ID** | 12 (ARM64) |
| **Features** | ARMv8 (64-bit) Family 8 Model 1 Revision 201 |

---

## 3. Graphics Processing Unit (GPU)

| Attribute | Detected Value |
| :--- | :--- |
| **GPU Name** | Qualcomm(R) Adreno(TM) X1-45 GPU |
| **PnP Device ID** | `ACPI\VEN_QCOM&DEV_0D17&SUBSYS_CRD08380&REV_002F\0` |
| **PnP Class** | Display (`{4d36e968-e325-11ce-bfc1-08002be10318}`) |
| **Driver Version** | 31.0.152.0 (Qualcomm Incorporated, `oem47.inf`) |
| **Status** | Started / Active |
| **DirectX / DirectML** | Supported via Adreno DirectX 12 / DirectML drivers |

---

## 4. Neural Processing Unit (NPU) & Hardware Accelerators

| Attribute | Detected Value |
| :--- | :--- |
| **Device Description** | **Snapdragon(R) X - X126100 - Qualcomm(R) Hexagon(TM) NPU** |
| **PnP Class** | `ComputeAccelerator` (`{f01a9d53-3ff6-48d2-9f97-c8a7004be10c}`) |
| **Instance ID** | `ACPI\QCOM0D0A\2&daba3ff&2` |
| **Manufacturer** | Qualcomm Technologies, Inc. |
| **Driver** | `oem48.inf` (Extension: `oem20.inf`) |
| **Device Status** | **Started / Operational** |
| **Verification Note** | NPU hardware is physically present and recognized as a Windows ComputeAccelerator device. |

---

## 5. Memory & Storage

| Component | Capacity | Available | Notes |
| :--- | :--- | :--- | :--- |
| **Physical RAM** | 16.0 GB (16,759,111,680 bytes) | ~8–10 GB usable dynamically | Sufficient for local inference, OCR, and PySide6 UI |
| **System Storage (`C:\`)**| 274 GB total | ~10 GB free | **Constraint Notice**: Free disk space is ~10 GB. Model weights and large binary wheels must be chosen conservatively to avoid disk exhaustion. |

---

## 6. Python Environment & Tooling

| Item | Value |
| :--- | :--- |
| **Python Executable** | `C:\Users\rishi\AppData\Local\Python\pythoncore-3.14-64\python.exe` |
| **Python Version** | Python 3.14.3 (tags/v3.14.3:323c59a, Feb 3 2026) |
| **Compiler / ABI** | MSC v.1944 64 bit (`AMD64`) running under Windows 11 ARM64 Prism Emulation |
| **Package Installer** | pip 25.3+ |
| **Test Runner** | pytest 9.1.1 (verified working) |
| **Pre-installed Libraries** | `numpy 2.5.3`, `pillow 12.1.1`, `opencv-python 5.0.0.93`, `pywin32 312`, `pypdf 6.13.1`, `lxml 6.1.3` |

---

## 7. AI & Automation Runtime Availability

| Runtime / Framework | Status | Compatibility Analysis |
| :--- | :--- | :--- |
| **Windows UI Automation (`uiautomation` / `pywin32`)** | **Available & Tested** | `pywin32` is native and fully functional on Windows 11. Provides primary UI inspection. |
| **Windows Native Media OCR (`Windows.Media.Ocr`)** | **Native Built-in** | Windows 11 includes native offline OCR APIs accessible via WinRT/Ctypes. |
| **PySide6 (Qt6)** | **Supported** | `pyside6` cp310-abi3 AMD64 wheels install and run seamlessly via Windows 11 Prism x64 emulator. |
| **ONNX Runtime (DirectML / CPU)** | **Compatible** | Available on PyPI for AMD64 under Windows 11; DirectML targets Qualcomm Adreno GPU. |
| **Qualcomm QNN / Hexagon Direct SDK** | **Hardware Present, Software SDK Required** | Hexagon NPU is operational at the driver level (`oem48.inf`). Direct QNN C++ DLLs/bindings require Qualcomm AI Engine / QNN SDK. DirectML or CPU fallback provides immediate out-of-the-box local execution. |
| **Local Speech-to-Text (STT)** | **Provider Interface Required** | Offline speech-to-text using local lightweight models (e.g. whisper-small/tiny on ONNX or native Windows Speech Recognition API / SAPI) works offline without cloud reliance. |

---

## 8. Potential Compatibility Issues & Mitigations

1. **Storage Headroom (~10 GB Free)**:
   - *Risk*: Downloading multi-gigabyte LLMs (e.g. 7B+ parameters) would rapidly exhaust system disk space.
   - *Mitigation*: Employ a tiered reasoning and perception architecture:
     - Use efficient, lightweight local models, native Windows APIs, and structured UI Automation / OCR pipelines.
     - Provide an abstract provider interface (`ReasoningProvider`) allowing local lightweight execution with an optional cloud API fallback when larger reasoning capabilities are required.
2. **Python 3.14 ABI Compatibility**:
   - *Risk*: Some C-extensions compiled only for Python 3.11/3.12 might lack pre-built wheels for 3.14.
   - *Mitigation*: Verified that `numpy`, `pillow`, `opencv-python`, `pywin32`, `pytest`, and `pyside6` (abi3) have working binary packages.
3. **No Fake NPU Indicator Rule**:
   - *Rule*: Per Section 6 Rule 3, the application must display actual runtime detection. When NPU is targeted through supported acceleration drivers, it indicates "NPU Active"; otherwise, it indicates "GPU (DirectML)" or "CPU Fallback".

---

## 9. Conclusion

The host environment is a **genuine Snapdragon X ARM64 PC** with Qualcomm Oryon 8-core CPU, Adreno GPU, and Hexagon NPU. The Python runtime and Windows APIs provide all necessary primitives to build the real, functional VisionPilot agent according to specification.
