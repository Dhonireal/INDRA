"""
VisionPilot Task History Viewer Dialog.

Provides interactive search, filtering by status and source, detailed inspection,
and safe transactional clearing of historical task records.
"""
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QScrollArea, QFrame, QMessageBox
)
from app.services.history_service import history_service
from app.ui.task_detail_dialog import TaskDetailDialog


class TaskHistoryItemWidget(QFrame):
    """Clickable row representing a historical task record."""

    def __init__(self, task: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task = task
        self.task_id = task.get("task_id", "")
        self.setProperty("class", "card-subtle")
        self.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #0284C7;
                background: #F8FAFC;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)

        cmd_text = self.task.get("user_command", "")
        cmd_lbl = QLabel(cmd_text, self)
        cmd_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #0F172A;")
        cmd_lbl.setWordWrap(True)

        status_str = self.task.get("status", "COMPLETED").upper()
        badge = QLabel(status_str, self)
        if status_str in ("COMPLETED", "VERIFIED_SUCCESS"):
            badge.setStyleSheet("background: #ECFDF5; color: #059669; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;")
        elif status_str in ("FAILED", "BLOCKED"):
            badge.setStyleSheet("background: #FEF2F2; color: #DC2626; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;")
        elif status_str in ("UNCERTAIN", "PARTIALLY_COMPLETED"):
            badge.setStyleSheet("background: #FFFBEB; color: #D97706; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;")
        else:
            badge.setStyleSheet("background: #F0F9FF; color: #0284C7; font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;")

        header.addWidget(cmd_lbl, 1)
        header.addWidget(badge)
        layout.addLayout(header)

        footer = QHBoxLayout()
        footer.setSpacing(10)

        created_str = self.task.get("created_at", "")
        time_part = created_str.split("T")[1][:8] if "T" in created_str else created_str
        date_part = created_str.split("T")[0] if "T" in created_str else ""
        time_lbl = QLabel(f"{date_part} {time_part}", self)
        time_lbl.setStyleSheet("font-size: 11px; color: #94A3B8;")

        source_lbl = QLabel(f"Source: {self.task.get('command_source', 'TEXT').upper()}", self)
        source_lbl.setStyleSheet("font-size: 11px; color: #64748B;")

        dur_sec = (self.task.get("duration_ms", 0.0) or 0.0) / 1000.0
        dur_text = f"{dur_sec:.2f}s" if dur_sec > 0 else "< 0.1s"
        dur_lbl = QLabel(f"Duration: {dur_text}", self)
        dur_lbl.setStyleSheet("font-size: 11px; color: #64748B;")

        footer.addWidget(time_lbl)
        footer.addWidget(source_lbl)
        footer.addWidget(dur_lbl)

        verif_status = self.task.get("verification_status")
        if verif_status:
            verif_lbl = QLabel(f"Verification: {verif_status}", self)
            verif_lbl.setStyleSheet("font-size: 11px; color: #0284C7;")
            footer.addWidget(verif_lbl)

        footer.addStretch()
        layout.addLayout(footer)

    def mousePressEvent(self, event) -> None:
        """Opens task details when row is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            dlg = TaskDetailDialog(self.task_id, self)
            dlg.exec()
        super().mousePressEvent(event)


class TaskHistoryDialog(QDialog):
    """Full task history dialog with search, status filtering, and clear functionality."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Task History & Audit Trail — VisionPilot")
        self.resize(750, 600)
        self.setMinimumSize(600, 480)
        self._init_ui()
        self._reload_tasks()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header Title
        title_row = QHBoxLayout()
        title = QLabel("Task History & Audit Trail", self)
        title.setStyleSheet("font-weight: 700; font-size: 16px; color: #0F172A;")
        title_row.addWidget(title)
        title_row.addStretch()

        self.clear_btn = QPushButton("Clear History", self)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #FEF2F2;
                color: #DC2626;
                border: 1px solid #FECACA;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #FEE2E2;
            }
        """)
        self.clear_btn.clicked.connect(self._handle_clear_history)
        title_row.addWidget(self.clear_btn)
        layout.addLayout(title_row)

        # Filter Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Search tasks by command text...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #0284C7;
            }
        """)
        self.search_input.textChanged.connect(self._reload_tasks)
        filter_bar.addWidget(self.search_input, 2)

        # Status Combo
        self.status_combo = QComboBox(self)
        self.status_combo.addItems([
            "All Statuses", "COMPLETED", "PARTIALLY_COMPLETED", "FAILED",
            "UNCERTAIN", "INTERRUPTED", "CANCELLED"
        ])
        self.status_combo.currentIndexChanged.connect(self._reload_tasks)
        filter_bar.addWidget(self.status_combo, 1)

        # Source Combo
        self.source_combo = QComboBox(self)
        self.source_combo.addItems(["All Sources", "TEXT", "VOICE"])
        self.source_combo.currentIndexChanged.connect(self._reload_tasks)
        filter_bar.addWidget(self.source_combo, 1)

        layout.addLayout(filter_bar)

        # Scroll Area for Task Items
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)

        self.empty_label = QLabel("No tasks found matching your criteria.", self.container)
        self.empty_label.setStyleSheet("font-size: 13px; color: #94A3B8; padding: 30px 0;")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.items_layout.addWidget(self.empty_label)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        # Footer
        footer = QHBoxLayout()
        self.count_label = QLabel("0 tasks recorded", self)
        self.count_label.setStyleSheet("font-size: 12px; color: #64748B;")
        footer.addWidget(self.count_label)
        footer.addStretch()

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _reload_tasks(self) -> None:
        """Queries repository with current search and filters and re-renders items."""
        search = self.search_input.text().strip()
        status_sel = self.status_combo.currentText()
        status = None if status_sel == "All Statuses" else status_sel

        source_sel = self.source_combo.currentText()
        source = None if source_sel == "All Sources" else source_sel

        records = history_service.list_tasks(limit=100, status=status, source=source, search=search)
        total_count = history_service.count_tasks(status=status, source=source, search=search)

        # Clear existing rows (except empty label)
        while self.items_layout.count() > 0:
            item = self.items_layout.takeAt(0)
            if item.widget() and item.widget() != self.empty_label:
                item.widget().deleteLater()

        self.count_label.setText(f"{total_count} task(s) recorded")

        if not records:
            self.empty_label.setVisible(True)
            self.items_layout.addWidget(self.empty_label)
        else:
            self.empty_label.setVisible(False)
            for rec in records:
                row = TaskHistoryItemWidget(rec.to_dict(), self.container)
                self.items_layout.addWidget(row)
            self.items_layout.addStretch()

    def _handle_clear_history(self) -> None:
        """Asks for confirmation before transactionally clearing history."""
        reply = QMessageBox.question(
            self,
            "Clear Task History",
            "Are you sure you want to permanently clear your local task history?\n\n"
            "This will delete all saved task commands, execution plans, action records, "
            "verification results, and audit trails.\n\n"
            "Your application settings and personal files will NOT be affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            history_service.clear_history()
            self._reload_tasks()
