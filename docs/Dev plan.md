Phase 0: Environment & Architecture (Done)
   ↓
Phase 1: Project Foundation (Directory layout, config, logging, event bus, state management, app/main.py)
   ↓
Phase 2: Desktop UI (PySide6 application shell, design tokens, command input, task status panel, settings)
   ↓
Phase 3: Text Command Pipeline (Typed schemas, command parser, structured task generation)
   ↓
Phase 4: Voice Pipeline (Audio capture, provider interface, local STT)
   ↓
Phase 5: Screen Perception (Screen capture, Windows UI Automation tree, OCR engine, unified ScreenContext)
   ↓
Phase 6: AI Task Planner (Context-aware action planning with structured schemas)
   ↓
Phase 7: Action Executor (Layered execution: UI Automation → OCR grounding → Native file APIs → Win32 input)
   ↓
Phase 8: Safety System (Risk classifier: SAFE, LOW, MEDIUM, HIGH, BLOCKED + interactive confirmation dialog)
   ↓
Phase 9: Verification & Recovery (Post-action state comparison, re-observation, retry limits)
   ↓
Phase 10: Task History (SQLite persistence, structured action logs, history UI)  hogya
   ↓
Phase 11: Snapdragon Optimization (Benchmarking, DirectML/NPU detection, hardware telemetry)  hogya
   ↓
Phase 12: Testing & Benchmarking (Pytest suite, mock environment, integration tests)  hogya
   ↓
Phase 13: Packaging (Build scripts, standalone executable)  hogya
   ↓
Phase 14: Demo & Documentation (End-to-end test of the primary workflow: find latest PDF, rename, move, verify)  hogya
