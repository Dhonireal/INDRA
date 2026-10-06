"""
VisionPilot Safety Confirmation Dialog Foundation.

Presents explicit user confirmation for sensitive or high-risk computer actions
strictly complying with Non-Negotiable Rule 5 (No Unlimited Autonomy) and Section 16 (Safety System).
"""
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from app.ui.styles.tokens import colors, spacing, typography


class ConfirmationDialog(QDialog):
    """Modal dialog prompting user approval before high/medium risk actions."""
    confirmed = Signal(bool)

    def __init__(
        self,
        action_type: str,
        target: str,
        risk_level: str = "HIGH",
        reason: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.action_type = action_type
        self.target = target
        self.risk_level = risk_level.upper()
        self.reason = reason
        self.setWindowTitle("Confirmation Required — VisionPilot Safety")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header with Alert Icon & Title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        icon_label = QLabel("⚠️", self)
        icon_label.setStyleSheet("font-size: 24px;")

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QLabel("Action Requires Your Confirmation", self)
        title_label.setStyleSheet(f"font-weight: {typography.weight_bold}; font-size: 15px; color: #0F172A;")

        subtitle_label = QLabel("VisionPilot safety policy intercepted a sensitive action.", self)
        subtitle_label.setStyleSheet("font-size: 12px; color: #64748B;")

        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)

        header_layout.addWidget(icon_label)
        header_layout.addLayout(title_col)
        header_layout.addStretch()

        # Details Card
        card = QFrame(self)
        card.setProperty("class", "card-subtle")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        # Risk badge
        risk_badge = QLabel(f"RISK LEVEL: {self.risk_level}", card)
        if self.risk_level == "HIGH":
            risk_badge.setProperty("class", "badge badge-error")
        elif self.risk_level == "MEDIUM":
            risk_badge.setProperty("class", "badge badge-warning")
        else:
            risk_badge.setProperty("class", "badge badge-active")
        risk_badge.setFixedWidth(120)
        risk_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        action_desc = QLabel(f"<b>Action:</b> {self.action_type}", card)
        action_desc.setStyleSheet("font-size: 13px; color: #0F172A;")

        target_desc = QLabel(f"<b>Target:</b> {self.target}", card)
        target_desc.setStyleSheet("font-size: 13px; color: #0F172A; word-break: break-all;")
        target_desc.setWordWrap(True)

        card_layout.addWidget(risk_badge)
        card_layout.addWidget(action_desc)
        card_layout.addWidget(target_desc)

        if self.reason:
            reason_lbl = QLabel(f"<b>Reason:</b> {self.reason}", card)
            reason_lbl.setStyleSheet("font-size: 12px; color: #64748B;")
            reason_lbl.setWordWrap(True)
            card_layout.addWidget(reason_lbl)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = QPushButton("Cancel Action", self)
        self.cancel_btn.clicked.connect(self._handle_reject)

        self.confirm_btn = QPushButton("Authorize Action", self)
        self.confirm_btn.setProperty("class", "primary")
        if self.risk_level == "HIGH":
            # Highlight with warning tone
            self.confirm_btn.setStyleSheet("background-color: #DC2626; border-color: #DC2626; color: white;")
        self.confirm_btn.clicked.connect(self._handle_accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(header_layout)
        layout.addWidget(card)
        layout.addLayout(btn_layout)

    def _handle_accept(self) -> None:
        self.confirmed.emit(True)
        self.accept()

    def _handle_reject(self) -> None:
        self.confirmed.emit(False)
        self.reject()
