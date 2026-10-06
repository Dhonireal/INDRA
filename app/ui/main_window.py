"""
VisionPilot Main Application Window.

Assembles the Desktop UI according to docs/design.md. Integrates the Header,
Command Input, Current Task Panel, Activity Panel, and Footer Status Bar.
Connected directly to AppState and EventBus without containing AI or automation logic.
"""
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QMessageBox
)

from datetime import datetime

from app.core.config import config
from app.core.logger import logger
from app.core.state import app_state, AppState, TaskStatus
from app.core.events import (
    event_bus, Event, SafetyConfirmationRequiredEvent,
    SafetyConfirmationResolvedEvent, ErrorEvent, TaskStatusChangedEvent
)
from app.services.task_service import command_service
from app.storage.repositories import command_repository
from app.agent.task_planner import task_planner
from app.perception.perception_engine import perception_engine
from app.agent.task_schema import PlanStatus, TaskPlan, RiskLevel
from app.execution.action_executor import action_executor
from app.voice.voice_service import voice_service
from app.agent.task_schema import CommandSource, CommandResult
from app.ui.styles.theme import get_stylesheet
from app.ui.styles.tokens import colors, typography, spacing
from app.ui.command_input import CommandInputWidget
from app.ui.task_panel import TaskPanel
from app.ui.activity_panel import ActivityPanel
from app.ui.confirmation_dialog import ConfirmationDialog
from app.ui.settings_window import SettingsWindow


class MainWindow(QMainWindow):
    """Primary VisionPilot desktop window."""

    # Thread-safe Qt signal for background state updates
    state_updated_signal = Signal(object)
    confirmation_requested_signal = Signal(object)
    error_occurred_signal = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{config.app_name} — {config.tagline}")
        self.resize(780, 820)
        self.setMinimumSize(680, 700)
        self.setStyleSheet(get_stylesheet())

        self._init_ui()
        self._wire_events()

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        window_layout = QVBoxLayout(central_widget)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)

        # 1. Header Bar
        header = QFrame(self)
        header.setProperty("class", "header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        header_layout.setSpacing(12)

        self.logo_label = QLabel(config.app_name, header)
        self.logo_label.setStyleSheet("font-weight: 700; font-size: 16px; color: #1E3A8A;")

        self.status_indicator = QLabel("● Ready", header)
        self.status_indicator.setProperty("class", "badge badge-ready")
        self.status_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.settings_btn = QPushButton("⚙ Settings", header)
        self.settings_btn.setProperty("class", "icon-btn")
        self.settings_btn.setAccessibleName("Open settings")
        self.settings_btn.clicked.connect(self._open_settings)

        header_layout.addWidget(self.logo_label)
        header_layout.addWidget(self.status_indicator)
        header_layout.addStretch()
        header_layout.addWidget(self.settings_btn)

        # 2. Main Scrollable Content Area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(32, 24, 32, 24)
        content_layout.setSpacing(20)

        # Hero Branding Section
        hero_layout = QVBoxLayout()
        hero_layout.setSpacing(4)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_title = QLabel("What can I do for you?", content_container)
        hero_title.setStyleSheet("font-weight: 700; font-size: 22px; color: #0F172A;")
        hero_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_subtitle = QLabel(config.tagline, content_container)
        hero_subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        hero_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_subtitle)

        # Error / Notification Banner
        self.error_banner = QFrame(content_container)
        self.error_banner.setProperty("class", "card-subtle")
        self.error_banner.setStyleSheet("background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 10px;")
        self.error_banner.setVisible(False)
        error_layout = QHBoxLayout(self.error_banner)
        error_layout.setContentsMargins(8, 4, 8, 4)

        self.error_msg_label = QLabel("", self.error_banner)
        self.error_msg_label.setStyleSheet("color: #991B1B; font-size: 12px; font-weight: 500;")
        self.error_msg_label.setWordWrap(True)

        dismiss_btn = QPushButton("✕", self.error_banner)
        dismiss_btn.setProperty("class", "icon-btn")
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.setStyleSheet("color: #991B1B; font-weight: bold;")
        dismiss_btn.clicked.connect(lambda: self.error_banner.setVisible(False))

        error_layout.addWidget(self.error_msg_label)
        error_layout.addStretch()
        error_layout.addWidget(dismiss_btn)

        # Command Input Card
        input_card = QFrame(content_container)
        input_card.setProperty("class", "card")
        input_card_layout = QVBoxLayout(input_card)
        input_card_layout.setContentsMargins(16, 16, 16, 16)

        self.command_input = CommandInputWidget(input_card)
        self.command_input.command_submitted.connect(self._handle_command_submitted)
        self.command_input.voice_triggered.connect(self._handle_voice_triggered)
        input_card_layout.addWidget(self.command_input)

        # Current Task Panel
        self.task_panel = TaskPanel(content_container)
        self.task_panel.cancel_requested.connect(self._handle_cancel_requested)
        self.task_panel.execute_requested.connect(self._handle_execute_plan)

        # Recent Activity Panel
        self.activity_panel = ActivityPanel(content_container)
        self._load_recent_history()

        content_layout.addLayout(hero_layout)
        content_layout.addWidget(self.error_banner)
        content_layout.addWidget(input_card)
        content_layout.addWidget(self.task_panel)
        content_layout.addWidget(self.activity_panel)
        content_layout.addStretch()

        scroll_area.setWidget(content_container)

        # 3. Footer / Hardware Telemetry Bar
        footer = QFrame(self)
        footer.setProperty("class", "footer")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 8)
        footer_layout.setSpacing(12)

        hw = app_state.hardware
        npu_status = "Hexagon NPU: Detected" if hw.npu_present else "NPU: Not Detected"

        self.hw_label = QLabel(f"Snapdragon AI PC  •  {hw.cpu_name}  •  {npu_status}", footer)
        self.hw_label.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 500;")

        self.runtime_label = QLabel(f"Runtime: {hw.active_runtime}", footer)
        self.runtime_label.setStyleSheet("color: #0284C7; font-size: 11px; font-weight: 500;")

        footer_layout.addWidget(self.hw_label)
        footer_layout.addStretch()
        footer_layout.addWidget(self.runtime_label)

        # Assemble Window Layout
        window_layout.addWidget(header)
        window_layout.addWidget(scroll_area)
        window_layout.addWidget(footer)

    def _wire_events(self) -> None:
        """Connects signals and subscribes to AppState and EventBus."""
        self.state_updated_signal.connect(self._on_state_updated)
        self.confirmation_requested_signal.connect(self._on_confirmation_requested)
        self.error_occurred_signal.connect(self._on_error_occurred)

        # Voice service signals
        voice_service.state_changed.connect(self._on_voice_state_changed)
        voice_service.transcript_ready.connect(self._on_voice_transcript_ready)
        voice_service.command_processed.connect(self._on_voice_command_processed)
        voice_service.error_occurred.connect(self._on_voice_error)

        # Subscribe to AppState mutations
        app_state.subscribe(lambda state: self.state_updated_signal.emit(state))

        # Subscribe to EventBus
        event_bus.subscribe(SafetyConfirmationRequiredEvent, lambda ev: self.confirmation_requested_signal.emit(ev))
        event_bus.subscribe(ErrorEvent, lambda ev: self.error_occurred_signal.emit(ev.user_message, ev.technical_details))

    def _load_recent_history(self) -> None:
        """Loads recent tasks from SQLite into activity panel."""
        self.activity_panel.load_recent()

    @Slot(object)
    def _on_state_updated(self, state: AppState) -> None:
        """Update UI based on current application state."""
        status = state.status

        # Update Header Status Badge
        if status in (TaskStatus.IDLE, TaskStatus.COMPLETED):
            self.status_indicator.setText(f"● {status.value.title()}")
            self.status_indicator.setProperty("class", "badge badge-ready")
        elif status == TaskStatus.FAILED:
            self.status_indicator.setText(f"● {status.value.title()}")
            self.status_indicator.setProperty("class", "badge badge-error")
        elif status == TaskStatus.WAITING_CONFIRMATION:
            self.status_indicator.setText("● Confirmation Required")
            self.status_indicator.setProperty("class", "badge badge-warning")
        elif status == TaskStatus.LISTENING:
            self.status_indicator.setText("● Listening...")
            self.status_indicator.setProperty("class", "badge badge-active")
        else:
            self.status_indicator.setText(f"● {status.value.title()}")
            self.status_indicator.setProperty("class", "badge badge-active")

        self.status_indicator.style().unpolish(self.status_indicator)
        self.status_indicator.style().polish(self.status_indicator)

        # Forward to Task Panel
        self.task_panel.update_from_state(state)

    @Slot(object)
    def _on_confirmation_requested(self, ev: SafetyConfirmationRequiredEvent) -> None:
        """Display safety confirmation modal."""
        logger.info(f"Displaying safety confirmation dialog for action {ev.action_type} on {ev.target}")
        dialog = ConfirmationDialog(
            action_type=ev.action_type,
            target=ev.target,
            risk_level=ev.risk_level,
            reason=ev.description,
            parent=self
        )
        approved = dialog.exec() == ConfirmationDialog.DialogCode.Accepted
        logger.info(f"User confirmation result: {'APPROVED' if approved else 'REJECTED'}")

        event_bus.publish(SafetyConfirmationResolvedEvent(
            task_id=ev.task_id,
            step_index=ev.step_index,
            approved=approved,
            reason="User accepted confirmation dialog" if approved else "User rejected confirmation dialog"
        ))

    @Slot(str, str)
    def _on_error_occurred(self, user_msg: str, tech_details: str) -> None:
        """Display error banner."""
        self.show_error(user_msg, tech_details)

    def show_error(self, user_message: str, technical_details: Optional[str] = None) -> None:
        """Displays user-friendly error banner."""
        self.error_msg_label.setText(user_message)
        self.error_banner.setVisible(True)
        if technical_details:
            logger.debug(f"Technical error diagnostic: {technical_details}")

    def _handle_command_submitted(self, command: str) -> None:
        """Process user command via CommandService and formulate structured plan via TaskPlanner."""
        logger.info(f"MainWindow delegating command to CommandService: {command}")
        # Dismiss existing error banner on new submission
        self.error_banner.setVisible(False)

        result = command_service.process_command(command)
        if result.success and result.task_request:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.activity_panel.add_activity(result.normalized_text, "PLANNING", timestamp)
            
            # Phase 6 AI Task Planner integration
            # Get current ScreenState from perception engine (fast/cached)
            screen_state = None
            try:
                screen_state = perception_engine.get_last_screen_state()
            except Exception as e:
                logger.debug(f"Perception state retrieval exception: {e}")

            # Generate validated TaskPlan
            cmd_req = command_service._active_commands.get(result.command_id)
            if cmd_req:
                plan = task_planner.create_plan(cmd_req, screen_state=screen_state)
                self._last_generated_plan = plan
                if plan.status == PlanStatus.READY:
                    self.activity_panel.add_activity(f"Plan Ready ({len(plan.steps)} steps)", "READY", timestamp)
                    
                    # Policy-compliant command execution lifecycle:
                    # 1. BLOCKED risk is never executed
                    if plan.risk_level == RiskLevel.BLOCKED:
                        logger.warning(f"Plan [{plan.plan_id}] contains BLOCKED operations and will not be executed.")
                        self.show_error("Execution Blocked: This action is prohibited by safety policy.")
                    # 2. SAFE / LOW risk: auto-execute if policy permits
                    elif plan.risk_level in (RiskLevel.SAFE, RiskLevel.LOW) and config.safety.auto_approve_low_risk:
                        logger.info(f"Auto-executing {plan.risk_level.value} risk plan [{plan.plan_id}] per safety policy.")
                        QTimer.singleShot(50, self._handle_execute_plan)
                    # 3. MEDIUM / HIGH risk (or confirmation required): Prompt user confirmation dialog
                    else:
                        logger.info(f"Plan [{plan.plan_id}] requires explicit confirmation (risk: {plan.risk_level.value}).")
                        dialog = ConfirmationDialog(
                            action_type=plan.steps[0].intent.capability if plan.steps else "EXECUTE_PLAN",
                            target=plan.goal,
                            risk_level=plan.risk_level.value,
                            reason=plan.summary,
                            parent=self
                        )
                        if dialog.exec() == ConfirmationDialog.DialogCode.Accepted:
                            logger.info(f"User approved execution of plan [{plan.plan_id}].")
                            QTimer.singleShot(50, self._handle_execute_plan)
                        else:
                            logger.info(f"User cancelled/rejected plan [{plan.plan_id}].")
                            app_state.mark_cancelled("Execution cancelled by user.")
                elif plan.status == PlanStatus.NEEDS_CLARIFICATION:
                    self.show_error(f"Clarification Required: {plan.clarification_question}")
                elif plan.status == PlanStatus.UNSUPPORTED:
                    self.show_error(f"Unsupported Action: {plan.summary}")
        else:
            self.show_error(result.message, result.error_code)

    def _handle_execute_plan(self) -> None:
        """Executes currently planned task through ActionExecutor."""
        plan = getattr(self, "_last_generated_plan", None)
        if not plan or plan.status != PlanStatus.READY:
            self.show_error("No ready plan available to execute.")
            return

        logger.info(f"MainWindow starting controlled execution of plan [{plan.plan_id}]")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.activity_panel.add_activity(f"Executing: {plan.goal[:30]}...", "EXECUTING", timestamp)

        results = action_executor.execute_plan(plan)
        self.activity_panel.load_recent()

    def _handle_cancel_requested(self, task_id: str) -> None:
        """Cancels active command/task."""
        logger.info(f"MainWindow cancelling task: {task_id}")
        if voice_service.audio_capture.is_recording:
            voice_service.cancel()
        task_planner.cancel()
        action_executor.cancel()
        command_service.cancel_command(task_id)

    def _handle_voice_triggered(self) -> None:
        """Handle microphone button click toggle (start/stop recording)."""
        if voice_service.audio_capture.is_recording:
            logger.info("Stopping voice recording...")
            self.command_input.set_recording_active(False)
            voice_service.stop_listening()
        else:
            logger.info("Starting voice recording on demand...")
            self.error_banner.setVisible(False)
            success = voice_service.start_listening()
            if success:
                self.command_input.set_recording_active(True)

    @Slot(str)
    def _on_voice_state_changed(self, state_str: str) -> None:
        """Syncs recording button visual state with voice service lifecycle."""
        if state_str == "RECORDING":
            self.command_input.set_recording_active(True)
        elif state_str in ("IDLE", "CANCELLED", "ERROR"):
            self.command_input.set_recording_active(False)

    @Slot(str, object)
    def _on_voice_transcript_ready(self, transcript: str, confidence: Optional[float]) -> None:
        """Displays recognized transcript in command editor for transparency."""
        self.command_input.editor.setText(transcript)
        if confidence is not None and confidence < 0.6:
            self.show_error(
                "Voice transcription may be inaccurate. Please review the command.",
                f"Confidence score: {confidence:.2f}"
            )

    @Slot(object)
    def _on_voice_command_processed(self, result: CommandResult) -> None:
        """Handles Phase 3 command result from voice pipeline."""
        self.command_input.set_recording_active(False)
        if result.success and result.task_request:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.activity_panel.add_activity(result.normalized_text, "READY", timestamp)
        else:
            self.show_error(result.message, result.error_code)

    @Slot(str, str)
    def _on_voice_error(self, user_msg: str, tech_details: str) -> None:
        """Handles voice errors gracefully."""
        self.command_input.set_recording_active(False)
        self.show_error(user_msg, tech_details)

    def _open_settings(self) -> None:
        """Open settings dialog."""
        settings_dialog = SettingsWindow(self)
        settings_dialog.exec()
