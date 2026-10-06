# Changelog

All notable changes to **VisionPilot** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-10-03

### Added
- **Core Loop Architecture**: Implemented full `See -> Understand -> Plan -> Act -> Verify` desktop AI agent pipeline.
- **Desktop UI**: Modern, accessible PySide6 light-themed desktop interface with `MainWindow`, `CommandInputWidget`, `TaskPanel`, `ActivityPanel`, `ConfirmationDialog`, and `SettingsWindow`.
- **Text Command Pipeline**: Robust command validation, normalization, and intent parsing with character limits and duplicate prevention.
- **Voice Pipeline**: Push-to-talk microphone audio capture, local Windows speech recognition, and typed text parity.
- **Screen Perception**: Hybrid perception fusing Windows UI Automation (UIA) tree hierarchy with local Windows Media OCR (`WinRT`) for coordinate-free element resolution.
- **AI Task Planner**: Structured plan formulation producing strictly typed `PlanStep` schemas with precondition/postcondition specifications.
- **Safety Engine & Gate**: Authoritative `ActionSafetyGate` with 5 categorical risk tiers (SAFE to BLOCKED), path traversal protection, interactive user confirmation binding, and unconditional blocking of permanent file deletion.
- **Controlled Action Executor**: Safe filesystem operations (`FileActionExecutor`) via native Python `pathlib`/`shutil`, window activation (`WindowExecutor`), and synthetic keyboard input (`KeyboardExecutor`).
- **Independent Verification**: Ground-truth `VerificationEngine` with bounded temporal polling evaluating real system state postconditions (`FileExists`, `FileAbsent`, `FileMoved`, `UIState`).
- **Bounded Recovery**: Capped retry and re-planning recovery engine (depth 3) with user escalation and abort mechanisms.
- **Task History & Audit**: Parameterized SQLite database (`data/visionpilot.db`) with WAL journal mode, automatic privacy redaction (`PrivacyRedactor`), and full inspection dialog.
- **Hardware Telemetry & Runtime Provider**: Snapdragon-aware hardware detection querying WMI/CIM for Snapdragon X Elite CPU, Adreno GPU, and Hexagon NPU with transparent CPU fallback.
- **Production Packaging**: PyInstaller standalone directory distribution (`dist/VisionPilot/`), portable self-contained ZIP (`release/VisionPilot-0.1.0-portable.zip`), and Inno Setup Windows installer (`release/VisionPilot-Setup-0.1.0.exe`).
- **Deterministic Demo Sandbox**: Isolated `demo_workspace/` environment with automated setup (`scripts/setup_demo_workspace.py`), reset (`scripts/reset_demo_workspace.py`), and flagship demo runner (`scripts/run_demo.py`).
- **Screenshots & Showcase Assets**: 12 authentic PySide6 UI captures in `assets/screenshots/`, pitch scripts, judge technical Q&A, and competition submission summaries.

### Reliability & Security
- 266 of 266 automated tests passing with zero regressions and zero skips.
- Prohibited arbitrary `eval()`, `exec()`, `os.system()`, or `shell=True` throughout execution pipeline.
- Parameterized all SQL statements to eliminate SQL injection vectors.
- Enforced strict hardware truthfulness: Hexagon NPU accurately reported as `DETECTED / NOT VERIFIED` under Prism emulation without fabricated performance claims.
