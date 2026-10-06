"""
VisionPilot Recent Activity Panel.

Renders persistent task execution history. Features empty state ("Your completed tasks will appear here.")
without inventing fake activity records. Provides click-to-inspect audit details and a full history dialog.
"""
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton
)
from app.services.history_service import history_service
from app.ui.task_detail_dialog import TaskDetailDialog
from app.ui.task_history_dialog import TaskHistoryDialog


class ActivityItemWidget(QFrame):
    """Row widget representing a single completed or recorded task."""

    def __init__(
        self,
        command: str,
        status: str,
        timestamp_str: str,
        duration: Optional[str] = None,
        task_id: Optional[str] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.task_id = task_id
        self.setProperty("class", "card-subtle")
        self.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
            }
            QFrame:hover {
                border-color: #0284C7;
                background: #F8FAFC;
            }
        """)
        if self.task_id:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)

        cmd_label = QLabel(command, self)
        cmd_label.setStyleSheet("font-weight: 500; font-size: 13px; color: #0F172A;")

        badge = QLabel(status.upper(), self)
        if status.upper() in ("SUCCESS", "COMPLETED", "VERIFIED"):
            badge.setProperty("class", "badge badge-ready")
        elif status.upper() in ("FAILED", "BLOCKED"):
            badge.setProperty("class", "badge badge-error")
        elif status.upper() in ("UNCERTAIN", "PARTIALLY_COMPLETED"):
            badge.setStyleSheet("background: #FFFBEB; color: #D97706; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;")
        else:
            badge.setProperty("class", "badge badge-active")

        header.addWidget(cmd_label, 1)
        header.addWidget(badge)

        footer = QHBoxLayout()
        footer.setSpacing(8)

        time_label = QLabel(timestamp_str, self)
        time_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        footer.addWidget(time_label)

        if duration:
            dur_label = QLabel(f"Duration: {duration}", self)
            dur_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
            footer.addWidget(dur_label)

        footer.addStretch()

        layout.addLayout(header)
        layout.addLayout(footer)

    def mousePressEvent(self, event) -> None:
        """Opens task details if task_id is present."""
        if self.task_id and event.button() == Qt.MouseButton.LeftButton:
            dlg = TaskDetailDialog(self.task_id, self)
            dlg.exec()
        super().mousePressEvent(event)


class ActivityPanel(QFrame):
    """Panel showing list of recent tasks with clean empty state and full history link."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setProperty("class", "card")
        self._init_ui()

    def _init_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(10)

        # Title row with "View All History" button
        title_layout = QHBoxLayout()
        title = QLabel("Recent Activity", self)
        title.setStyleSheet("font-weight: 600; font-size: 14px; color: #0F172A;")
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.history_btn = QPushButton("View All History ↗", self)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0284C7;
                border: none;
                font-size: 12px;
                font-weight: 600;
                padding: 2px 4px;
            }
            QPushButton:hover {
                color: #0369A1;
                text-decoration: underline;
            }
        """)
        self.history_btn.clicked.connect(self._open_history_dialog)
        title_layout.addWidget(self.history_btn)

        self.main_layout.addLayout(title_layout)

        # Empty state label
        self.empty_label = QLabel("Your completed tasks will appear here.", self)
        self.empty_label.setStyleSheet("font-size: 13px; color: #94A3B8; padding: 12px 0;")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addWidget(self.empty_label)

        # Container for task items
        self.items_container = QWidget(self)
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        self.main_layout.addWidget(self.items_container)

    def load_recent(self) -> None:
        """Loads recent tasks from TaskHistoryService."""
        self.clear()
        tasks = history_service.list_tasks(limit=5)
        if not tasks:
            self.empty_label.setVisible(True)
            return

        for t in reversed(tasks):
            created_str = t.created_at
            time_part = created_str.split("T")[1][:8] if "T" in created_str else created_str
            dur_sec = t.duration_ms / 1000.0
            dur_str = f"{dur_sec:.1f}s" if dur_sec > 0 else None
            self.add_activity(
                command=t.user_command,
                status=t.status,
                timestamp_str=time_part,
                duration=dur_str,
                task_id=t.task_id
            )

    def add_activity(
        self,
        command: str,
        status: str,
        timestamp_str: str,
        duration: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> None:
        """Add a real task item to the activity list."""
        self.empty_label.setVisible(False)
        item = ActivityItemWidget(command, status, timestamp_str, duration, task_id=task_id, parent=self.items_container)
        self.items_layout.insertWidget(0, item)

    def clear(self) -> None:
        """Clear all activity items and show empty state."""
        while self.items_layout.count() > 0:
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.empty_label.setVisible(True)

    def _open_history_dialog(self) -> None:
        """Opens full task history modal."""
        dlg = TaskHistoryDialog(self)
        dlg.exec()
        # Refresh recent tasks upon closing history dialog (in case items were cleared)
        self.load_recent()
