
---

# 5. `file-structure.md`

```md
# VisionPilot — Project File Structure

## 1. Root Structure

```text
visionpilot/
│
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CHANGELOG.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── requirements.txt
│
├── app/
│   ├── main.py
│   │
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── command_input.py
│   │   ├── task_panel.py
│   │   ├── confirmation_dialog.py
│   │   ├── settings_window.py
│   │   └── styles/
│   │       ├── theme.py
│   │       └── tokens.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── events.py
│   │   ├── exceptions.py
│   │   ├── logger.py
│   │   └── state.py
│   │
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── audio_capture.py
│   │   ├── stt_provider.py
│   │   ├── voice_service.py
│   │   └── providers/
│   │       └── local_stt.py
│   │
│   ├── perception/
│   │   ├── __init__.py
│   │   ├── screen_capture.py
│   │   ├── screen_context.py
│   │   ├── ui_detector.py
│   │   │
│   │   ├── ocr/
│   │   │   ├── ocr_provider.py
│   │   │   └── local_ocr.py
│   │   │
│   │   └── vision/
│   │       ├── vision_provider.py
│   │       └── local_vision.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── command_parser.py
│   │   ├── task_planner.py
│   │   ├── task_schema.py
│   │   ├── context_manager.py
│   │   └── providers/
│   │       ├── reasoning_provider.py
│   │       └── local_reasoning.py
│   │
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── action.py
│   │   ├── action_executor.py
│   │   ├── mouse_controller.py
│   │   ├── keyboard_controller.py
│   │   ├── window_controller.py
│   │   └── file_operations.py
│   │
│   ├── safety/
│   │   ├── __init__.py
│   │   ├── risk_classifier.py
│   │   ├── permission_manager.py
│   │   ├── confirmation_service.py
│   │   └── policy.py
│   │
│   ├── verification/
│   │   ├── __init__.py
│   │   ├── verifier.py
│   │   ├── state_comparator.py
│   │   └── recovery.py
│   │
│   ├── hardware/
│   │   ├── device_detector.py
│   │   ├── runtime_detector.py
│   │   ├── acceleration.py
│   │   └── benchmark.py
│   │
│   ├── storage/
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── repositories.py
│   │   └── migrations/
│   │
│   └── services/
│       ├── task_service.py
│       ├── history_service.py
│       └── notification_service.py
│
├── tests/
│   ├── unit/
│   │   ├── test_planner.py
│   │   ├── test_safety.py
│   │   ├── test_verification.py
│   │   ├── test_ocr.py
│   │   └── test_file_operations.py
│   │
│   ├── integration/
│   │   ├── test_voice_pipeline.py
│   │   ├── test_agent_pipeline.py
│   │   └── test_execution_pipeline.py
│   │
│   └── fixtures/
│
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── design.md
│   ├── tech-stack.md
│   ├── file-structure.md
│   ├── setup.md
│   ├── voice-pipeline.md
│   ├── vision-pipeline.md
│   ├── agent-workflow.md
│   ├── safety-and-permissions.md
│   ├── snapdragon-optimization.md
│   └── benchmarks.md
│
├── assets/
│   ├── icons/
│   ├── screenshots/
│   ├── demo/
│   └── diagrams/
│
├── scripts/
│   ├── setup.py
│   ├── benchmark.py
│   ├── check_environment.py
│   └── run_demo.py
│
├── models/
│   └── README.md
│
└── packaging/
    ├── build_windows.py
    └── installer/