"""
Unit tests for VisionPilot Phase 2 Desktop UI Foundation.

Tests:
1. Main window construction
2. Application startup & layout
3. Command submission signal/event emission
4. UI state transitions (IDLE, ANALYZING, EXECUTING, COMPLETED, FAILED)
5. Status indicator rendering
6. Empty state rendering (Task panel & Activity panel)
7. Error state banner presentation
8. Settings window construction & tab structure
9. Confirmation dialog construction & action authorization
10. Hardware/runtime status display logic (honest NPU/CPU/GPU representation)
11. Keyboard interaction handling (Enter key submission)
"""
import sys
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeyEvent

from app.core.config import config
from app.core.state import app_state, TaskStatus, HardwareState
from app.core.events import event_bus, TaskCreatedEvent, SafetyConfirmationRequiredEvent
from app.ui.main_window import MainWindow
from app.ui.command_input import CommandInputWidget, CommandTextEdit
from app.ui.task_panel import TaskPanel
from app.ui.activity_panel import ActivityPanel
from app.ui.confirmation_dialog import ConfirmationDialog
from app.ui.settings_window import SettingsWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance runs across tests."""
    app = QApplication.instance()
    if app is None:
        # Offscreen platform for headless test execution
        app = QApplication(["-platform", "offscreen"])
    yield app


@pytest.fixture
def clean_state():
    """Reset app_state and event_bus between tests."""
    app_state.reset()
    event_bus.clear()
    yield
    app_state.reset()
    event_bus.clear()


class TestMainWindow:
    def test_main_window_construction(self, qapp, clean_state) -> None:
        window = MainWindow()
        assert window.windowTitle().startswith(config.app_name)
        assert window.logo_label.text() == config.app_name
        assert window.status_indicator.text() == "● Ready"
        assert window.command_input is not None
        assert window.task_panel is not None
        assert window.activity_panel is not None
        assert window.hw_label is not None
        assert window.runtime_label is not None
        window.close()

    def test_command_submission_event(self, qapp, clean_state) -> None:
        window = MainWindow()
        received_events = []

        event_bus.subscribe(TaskCreatedEvent, lambda ev: received_events.append(ev))

        # Type in editor
        window.command_input.editor.setPlainText("Find latest PDF and move to Research")
        # Click send
        window.command_input.send_btn.click()

        assert len(received_events) == 1
        assert received_events[0].command == "Find latest PDF and move to Research"
        assert received_events[0].source == "text"
        assert window.command_input.editor.toPlainText() == ""  # Input was cleared
        window.close()

    def test_ui_state_transitions(self, qapp, clean_state) -> None:
        window = MainWindow()

        # Update state to ANALYZING
        app_state.update_status(TaskStatus.ANALYZING, "Analyzing current screen")
        qapp.processEvents()
        assert "Analyzing" in window.status_indicator.text()

        # Update state to EXECUTING
        app_state.update_status(TaskStatus.EXECUTING, "Executing click")
        qapp.processEvents()
        assert "Executing" in window.status_indicator.text()

        # Update state to COMPLETED
        app_state.mark_completed("Done")
        qapp.processEvents()
        assert "Completed" in window.status_indicator.text()
        window.close()

    def test_error_banner_display(self, qapp, clean_state) -> None:
        window = MainWindow()
        window.show()
        assert not window.error_banner.isVisible()

        window.show_error("Could not find requested file.", "FileNotFoundError at /downloads")
        assert window.error_banner.isVisible()
        assert "Could not find requested file." in window.error_msg_label.text()
        window.close()


class TestCommandInput:
    def test_enter_key_submits(self, qapp, clean_state) -> None:
        widget = CommandInputWidget()
        submitted = []
        widget.command_submitted.connect(lambda cmd: submitted.append(cmd))

        widget.editor.setPlainText("Open Downloads")

        # Simulate Enter key press
        key_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        widget.editor.keyPressEvent(key_event)

        assert len(submitted) == 1
        assert submitted[0] == "Open Downloads"

    def test_disabled_state(self, qapp) -> None:
        widget = CommandInputWidget()
        widget.set_enabled_state(False)
        assert not widget.editor.isEnabled()
        assert not widget.send_btn.isEnabled()
        assert not widget.mic_btn.isEnabled()


class TestTaskPanel:
    def test_empty_task_panel(self, qapp, clean_state) -> None:
        panel = TaskPanel()
        assert panel.command_label.text() == "No active task"
        assert panel.progress_bar.isHidden()
        assert panel.status_badge.text() in ("READY", "IDLE")

    def test_active_plan_progress_rendering(self, qapp, clean_state) -> None:
        panel = TaskPanel()
        panel.show()
        app_state.set_task("t-1", "Rename file")
        app_state.set_plan([
            {"action_type": "INSPECT"},
            {"action_type": "RENAME"},
            {"action_type": "VERIFY"}
        ])
        panel.update_from_state(app_state)

        assert panel.command_label.text() == '"Rename file"'
        assert not panel.progress_bar.isHidden()
        # Step 0 of 3 => ~33%
        assert panel.progress_bar.value() == 33
        assert "Step 1 of 3: INSPECT" in panel.step_label.text()
        panel.close()


class TestActivityPanel:
    def test_empty_activity_state(self, qapp) -> None:
        panel = ActivityPanel()
        assert not panel.empty_label.isHidden()
        assert panel.empty_label.text() == "Your completed tasks will appear here."

    def test_add_activity_hides_empty_label(self, qapp) -> None:
        panel = ActivityPanel()
        panel.add_activity("Organize PDF reports", "SUCCESS", "17:30:00", "2.4s")
        assert panel.empty_label.isHidden()
        assert panel.items_layout.count() == 1


class TestConfirmationDialog:
    def test_dialog_construction_and_details(self, qapp) -> None:
        dialog = ConfirmationDialog(
            action_type="DELETE_FILE",
            target="Research/report.pdf",
            risk_level="HIGH",
            reason="User commanded deletion"
        )
        assert dialog.action_type == "DELETE_FILE"
        assert dialog.target == "Research/report.pdf"
        assert dialog.risk_level == "HIGH"
        assert dialog.confirm_btn is not None
        assert dialog.cancel_btn is not None


class TestSettingsWindow:
    def test_settings_tab_structure(self, qapp) -> None:
        dialog = SettingsWindow()
        assert dialog.tabs.count() == 6
        tab_names = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        assert "General" in tab_names
        assert "Automation" in tab_names
        assert "Privacy" in tab_names
        assert "Voice" in tab_names
        assert "AI Runtime" in tab_names
        assert "About" in tab_names


class TestHardwareDisplay:
    def test_hardware_status_formatting(self, qapp, clean_state) -> None:
        app_state.set_hardware(HardwareState(
            cpu_name="Snapdragon X Oryon",
            gpu_name="Adreno X1-45",
            npu_name="Hexagon NPU",
            npu_present=True,
            active_runtime="Windows Native (CPU/DirectX)"
        ))
        window = MainWindow()
        assert "Snapdragon X Oryon" in window.hw_label.text()
        assert "Hexagon NPU: Detected" in window.hw_label.text()
        assert "Windows Native (CPU/DirectX)" in window.runtime_label.text()
        # Verify no false claim of "NPU Accelerated"
        assert "NPU Accelerated" not in window.hw_label.text()
        assert "NPU Accelerated" not in window.runtime_label.text()
        window.close()
