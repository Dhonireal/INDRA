"""
VisionPilot Command Input Component.

Provides a multiline command editor, send button, microphone trigger button,
and keyboard shortcut handling (Enter / Ctrl+Enter).
Emits Qt signals and publishes Phase 1 TaskCreatedEvent without executing AI actions in Phase 2.
"""
from typing import Optional
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel
)
from app.core.events import event_bus, CommandSubmittedEvent, TaskCreatedEvent
from app.core.logger import logger


class CommandTextEdit(QTextEdit):
    """Custom QTextEdit intercepting Enter / Ctrl+Enter for submission."""
    submit_requested = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # If Shift+Enter, allow newline
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                # Enter or Ctrl+Enter submits
                event.accept()
                self.submit_requested.emit()
                return
        super().keyPressEvent(event)


class CommandInputWidget(QWidget):
    """Command input container with editor, voice trigger, and submit controls."""
    command_submitted = Signal(str)
    voice_triggered = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Editor
        self.editor = CommandTextEdit(self)
        self.editor.setPlaceholderText("Tell VisionPilot what you want to do... (Press Enter to submit, Shift+Enter for newline)")
        self.editor.setFixedHeight(74)
        self.editor.submit_requested.connect(self._handle_submit)

        # Controls bar below input
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(4, 0, 4, 0)
        controls_layout.setSpacing(8)

        # Voice Button (Phase 4 Voice pipeline integration)
        self.mic_btn = QPushButton("🎙️", self)
        self.mic_btn.setProperty("class", "mic-btn")
        self.mic_btn.setToolTip("Voice Command (Click to speak)")
        self.mic_btn.setAccessibleName("Microphone voice command button")
        self.mic_btn.clicked.connect(self._handle_mic_clicked)

        # Hint Label
        self.hint_label = QLabel("Shift+Enter for newline", self)
        self.hint_label.setStyleSheet("color: #94A3B8; font-size: 11px;")

        # Submit / Send Button
        self.send_btn = QPushButton("Send", self)
        self.send_btn.setProperty("class", "primary")
        self.send_btn.setAccessibleName("Submit command")
        self.send_btn.setFixedWidth(80)
        self.send_btn.clicked.connect(self._handle_submit)

        controls_layout.addWidget(self.mic_btn)
        controls_layout.addWidget(self.hint_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.send_btn)

        layout.addWidget(self.editor)
        layout.addLayout(controls_layout)

    def _handle_submit(self) -> None:
        text = self.editor.toPlainText()
        if not text.strip():
            # Emit to let service trigger proper validation failure notification
            self.command_submitted.emit(text)
            return

        self.send_btn.setEnabled(False)
        try:
            logger.info("Command text submitted via UI")
            self.command_submitted.emit(text)
            event_bus.publish(CommandSubmittedEvent(
                raw_text=text,
                source="text"
            ))
            # Clear input field after successful submission
            self.editor.clear()
        finally:
            self.send_btn.setEnabled(True)

    def _handle_mic_clicked(self) -> None:
        logger.info("Microphone button clicked.")
        self.voice_triggered.emit()

    def set_recording_active(self, is_active: bool) -> None:
        """Updates mic button appearance when audio recording is active."""
        if is_active:
            self.mic_btn.setText("⏹️")
            self.mic_btn.setToolTip("Recording... Click to stop")
            self.mic_btn.setStyleSheet("background-color: #FEE2E2; border: 1.5px solid #EF4444; color: #DC2626;")
        else:
            self.mic_btn.setText("🎙️")
            self.mic_btn.setToolTip("Voice Command (Click to speak)")
            self.mic_btn.setStyleSheet("")

    def set_enabled_state(self, enabled: bool) -> None:
        """Enable or disable input components."""
        self.editor.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)
        self.mic_btn.setEnabled(enabled)
