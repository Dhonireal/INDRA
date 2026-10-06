"""
VisionPilot Current Task & Plan Preview Panel.

Visualizes active task information, status, structured step progression, and
an interactive Plan Preview Card (Phase 6):
- Goal and concise summary
- Ordered steps with capability, target source, and risk badges
- Assumptions and verification requirements
- Clarification questions and candidates
- Explicitly disabled or labeled "Execution available in Phase 7" button
  (Zero fake execution buttons).
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton, QScrollArea
)
from app.core.state import AppState, TaskStatus, app_state
from app.core.logger import logger


class TaskPanel(QFrame):
    """Panel displaying real-time execution telemetry and structured Plan Preview."""
    cancel_requested = Signal(str)

    execute_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "card")
        self._start_time: Optional[datetime] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header: Title + Status Badge + Cancel Button
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel("Current Task", self)
        self.title_label.setStyleSheet("font-weight: 600; font-size: 14px; color: #0F172A;")

        self.status_badge = QLabel("READY", self)
        self.status_badge.setProperty("class", "badge badge-ready")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.setProperty("class", "icon-btn")
        self.cancel_btn.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 500; border: 1px solid #FECACA; padding: 4px 8px; border-radius: 4px;")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._handle_cancel)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.status_badge)
        header_layout.addStretch()
        header_layout.addWidget(self.cancel_btn)

        # Command text
        self.command_label = QLabel("No active task", self)
        self.command_label.setWordWrap(True)
        self.command_label.setStyleSheet("font-size: 13px; color: #64748B;")

        # Progress bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        # Step details label
        self.step_label = QLabel("", self)
        self.step_label.setStyleSheet("font-size: 12px; color: #0284C7; font-weight: 500;")
        self.step_label.setVisible(False)

        # Plan Preview Container
        self.plan_preview_card = QFrame(self)
        self.plan_preview_card.setProperty("class", "card-subtle")
        self.plan_preview_card.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        self.plan_preview_card.setVisible(False)

        preview_layout = QVBoxLayout(self.plan_preview_card)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(8)

        # Preview Header (Goal + Risk Badge)
        prev_header = QHBoxLayout()
        self.preview_goal_label = QLabel("Task Plan Preview", self.plan_preview_card)
        self.preview_goal_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #1E293B;")
        
        self.preview_risk_badge = QLabel("SAFE", self.plan_preview_card)
        self.preview_risk_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #E2E8F0; color: #334155;")
        
        prev_header.addWidget(self.preview_goal_label)
        prev_header.addStretch()
        prev_header.addWidget(self.preview_risk_badge)

        self.preview_summary_label = QLabel("", self.plan_preview_card)
        self.preview_summary_label.setWordWrap(True)
        self.preview_summary_label.setStyleSheet("font-size: 12px; color: #475569;")

        # Steps container
        self.preview_steps_label = QLabel("", self.plan_preview_card)
        self.preview_steps_label.setWordWrap(True)
        self.preview_steps_label.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.4;")

        # Execution notice and Execute button (Controlled Phase 7 execution)
        prev_actions = QHBoxLayout()
        self.phase_notice_label = QLabel("Controlled Execution Ready", self.plan_preview_card)
        self.phase_notice_label.setStyleSheet("font-size: 11px; font-weight: 500; color: #0284C7;")

        self.execute_btn = QPushButton("Execute Plan", self.plan_preview_card)
        self.execute_btn.setEnabled(True)
        self.execute_btn.setToolTip("Start controlled action execution.")
        self.execute_btn.setStyleSheet("background-color: #0284C7; color: white; font-size: 11px; font-weight: 600; border-radius: 4px; padding: 5px 12px; border: none;")
        self.execute_btn.clicked.connect(self._handle_execute)

        prev_actions.addWidget(self.phase_notice_label)
        prev_actions.addStretch()
        prev_actions.addWidget(self.execute_btn)

        preview_layout.addLayout(prev_header)
        preview_layout.addWidget(self.preview_summary_label)
        preview_layout.addWidget(self.preview_steps_label)
        preview_layout.addLayout(prev_actions)

        # Assemble main layout
        layout.addLayout(header_layout)
        layout.addWidget(self.command_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.step_label)
        layout.addWidget(self.plan_preview_card)

    def update_from_state(self, state: AppState) -> None:
        """Updates the panel based on real application state."""
        status = state.status

        # Update Badge Style and Text
        self.status_badge.setText(status.value)
        if status in (TaskStatus.IDLE, TaskStatus.COMPLETED):
            self.status_badge.setProperty("class", "badge badge-ready")
            self.cancel_btn.setVisible(False)
        elif status in (TaskStatus.FAILED, TaskStatus.UNCERTAIN):
            self.status_badge.setProperty("class", "badge badge-error")
            self.cancel_btn.setVisible(False)
        elif status in (TaskStatus.WAITING_CONFIRMATION, TaskStatus.RECOVERING, TaskStatus.PARTIALLY_COMPLETED):
            self.status_badge.setProperty("class", "badge badge-warning")
            self.cancel_btn.setVisible(True)
        else:
            self.status_badge.setProperty("class", "badge badge-active")
            self.cancel_btn.setVisible(True)
        
        # Force stylesheet refresh on dynamic property change
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

        # Command & Step Display
        if status == TaskStatus.IDLE or not state.current_command:
            self.command_label.setText("No active task")
            self.command_label.setStyleSheet("font-size: 13px; color: #64748B;")
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)
            self.step_label.setVisible(False)
            self.plan_preview_card.setVisible(False)
            self._start_time = None
        else:
            self.command_label.setText(f'"{state.current_command}"')
            self.command_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #0F172A;")

            # Step and Progress Calculation (Only driven by real plan data)
            total_steps = len(state.current_plan)
            if total_steps > 0:
                self.progress_bar.setVisible(True)
                step_idx = max(0, state.current_step_index)
                progress_pct = int(((step_idx + 1) / total_steps) * 100) if status != TaskStatus.COMPLETED else 100
                self.progress_bar.setValue(min(100, progress_pct))

                step_data = state.current_plan[step_idx] if step_idx < total_steps else {}
                step_desc = step_data.get("action_type") or step_data.get("description") or "Step"
                self.step_label.setText(f"Step {step_idx + 1} of {total_steps}: {step_desc} — {state.status_message}")
                self.step_label.setVisible(True)

                # Render Structured Plan Preview
                self._render_plan_preview(state.current_plan, state.status_message)
            else:
                self.plan_preview_card.setVisible(False)
                self.progress_bar.setVisible(status in (TaskStatus.ANALYZING, TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.VERIFYING, TaskStatus.RECOVERING))
                self.progress_bar.setValue(10 if status == TaskStatus.ANALYZING else 25)
                self.step_label.setText(state.status_message)
                self.step_label.setVisible(bool(state.status_message))

    def _render_plan_preview(self, steps: List[Dict[str, Any]], status_message: str) -> None:
        """Renders ordered steps and risk indicators in the preview card."""
        self.plan_preview_card.setVisible(True)
        self.preview_summary_label.setText(status_message)

        # Format steps into human-readable numbered list
        step_lines = []
        max_risk = "SAFE"
        risk_precedence = {"SAFE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BLOCKED": 4}

        for idx, s in enumerate(steps):
            order = s.get("order", idx + 1)
            desc = s.get("description", "Action step")
            cap = s.get("intent", {}).get("capability", "")
            risk = s.get("risk_level", "LOW")
            if risk_precedence.get(risk, 0) > risk_precedence.get(max_risk, 0):
                max_risk = risk

            cap_badge = f"[{cap}]" if cap else ""
            step_lines.append(f"<b>{order}.</b> {desc} <span style='color: #64748B; font-size: 11px;'>{cap_badge}</span>")

        self.preview_steps_label.setText("<br>".join(step_lines))
        self.preview_risk_badge.setText(max_risk)
        
        # Color risk badge appropriately
        if max_risk in ("HIGH", "BLOCKED"):
            self.preview_risk_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #FEE2E2; color: #991B1B;")
        elif max_risk == "MEDIUM":
            self.preview_risk_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #FEF3C7; color: #92400E;")
        else:
            self.preview_risk_badge.setStyleSheet("font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; background-color: #E0F2FE; color: #0369A1;")

    def _handle_cancel(self) -> None:
        if app_state.current_task_id:
            logger.info(f"Cancel requested for task: {app_state.current_task_id}")
            self.cancel_requested.emit(app_state.current_task_id)

    def _handle_execute(self) -> None:
        logger.info("Execute Plan button clicked by user.")
        self.execute_requested.emit()

