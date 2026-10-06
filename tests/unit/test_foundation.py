"""
Unit tests for VisionPilot Phase 1 Foundation.

Tests configuration, logger redaction, event bus, app state, exceptions,
and authentic device detection.
"""
import pytest
from pathlib import Path
from app.core.config import load_config, AppConfig
from app.core.logger import setup_logger, RedactingFormatter
from app.core.events import EventBus, Event, TaskCreatedEvent, TaskStatusChangedEvent
from app.core.state import AppState, TaskStatus, HardwareState
from app.core.exceptions import (
    VisionPilotError, SafetyViolationError, PerceptionError,
    PlanningError, ExecutionError, VerificationError
)
from app.hardware.device_detector import DeviceDetector


class TestConfig:
    def test_default_config_initialization(self) -> None:
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.app_name == "VisionPilot"
        assert cfg.data_dir.exists()
        assert cfg.logs_dir.exists()
        assert cfg.models_dir.exists()
        assert cfg.safety.confirm_high_risk is True
        assert cfg.safety.max_consecutive_retries == 3


class TestLogger:
    def test_redaction_formatter(self) -> None:
        formatter = RedactingFormatter(fmt="%(message)s")
        import logging

        # Test password redaction
        rec1 = logging.LogRecord("test", logging.INFO, "path", 1, "User entered password=SuperSecret123!", (), None)
        assert "SuperSecret123!" not in formatter.format(rec1)
        assert "[REDACTED]" in formatter.format(rec1)

        # Test token redaction
        rec2 = logging.LogRecord("test", logging.INFO, "path", 1, "Using Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", (), None)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in formatter.format(rec2)
        assert "[REDACTED]" in formatter.format(rec2)

        # Test api key redaction
        rec3 = logging.LogRecord("test", logging.INFO, "path", 1, "api_key='AIzaSyD-1234567890abcdef'", (), None)
        assert "AIzaSyD-1234567890abcdef" not in formatter.format(rec3)
        assert "[REDACTED]" in formatter.format(rec3)


class TestEventBus:
    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received_events = []

        def handler(event: TaskCreatedEvent) -> None:
            received_events.append(event)

        bus.subscribe(TaskCreatedEvent, handler)
        ev = TaskCreatedEvent(task_id="t-101", command="Find latest PDF", source="voice")
        bus.publish(ev)

        assert len(received_events) == 1
        assert received_events[0].task_id == "t-101"
        assert received_events[0].command == "Find latest PDF"

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received = []

        def handler(event: TaskStatusChangedEvent) -> None:
            received.append(event)

        bus.subscribe(TaskStatusChangedEvent, handler)
        bus.publish(TaskStatusChangedEvent(task_id="t-1", old_status="IDLE", new_status="ANALYZING"))
        assert len(received) == 1

        bus.unsubscribe(TaskStatusChangedEvent, handler)
        bus.publish(TaskStatusChangedEvent(task_id="t-1", old_status="ANALYZING", new_status="PLANNING"))
        assert len(received) == 1

    def test_handler_error_isolation(self) -> None:
        bus = EventBus()
        calls = []

        def faulty_handler(ev: Event) -> None:
            raise ValueError("Bug in listener")

        def normal_handler(ev: Event) -> None:
            calls.append(True)

        bus.subscribe(Event, faulty_handler)
        bus.subscribe(Event, normal_handler)
        bus.publish(Event())

        assert len(calls) == 1


class TestAppState:
    def test_initial_state(self) -> None:
        state = AppState()
        assert state.status == TaskStatus.IDLE
        assert state.current_task_id is None
        assert state.pending_confirmation is None

    def test_task_lifecycle(self) -> None:
        state = AppState()
        notified = []

        state.subscribe(lambda s: notified.append(s.status))

        state.set_task("task-123", "Move PDF to Research")
        assert state.status == TaskStatus.ANALYZING
        assert state.current_command == "Move PDF to Research"

        state.set_plan([{"action": "CLICK", "target": "PDF"}])
        assert state.status == TaskStatus.EXECUTING
        assert state.current_step_index == 0

        state.advance_step(1, "Moving file")
        assert state.current_step_index == 1

        state.mark_completed("Done")
        assert state.status == TaskStatus.COMPLETED

        state.reset()
        assert state.status == TaskStatus.IDLE
        assert state.current_task_id is None
        assert len(notified) > 0


class TestExceptions:
    def test_user_friendly_message(self) -> None:
        err = SafetyViolationError("Internal: blocked by policy regex on 'format c:'", "Command was blocked for safety.")
        assert err.get_user_friendly_message() == "Command was blocked for safety."
        assert "format c:" in str(err)

        err_default = ExecutionError("Low level Win32 SendInput failure code 5")
        assert err_default.get_user_friendly_message() == "VisionPilot was unable to complete the requested computer action."


class TestDeviceDetector:
    def test_detect_returns_valid_hardware_state(self) -> None:
        detector = DeviceDetector()
        hw = detector.detect()
        assert isinstance(hw, HardwareState)
        assert hw.cpu_name
        assert hw.gpu_name
        assert isinstance(hw.npu_present, bool)
        assert hw.active_runtime
