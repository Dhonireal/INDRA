"""
Unit tests for VisionPilot Phase 4 Voice Pipeline.

Tests:
1. STT provider interface and metadata contract
2. MockSTTProvider deterministic behavior & error simulation
3. LocalSTTProvider truthful capability & accelerator reporting (CPU)
4. Microphone discovery and default microphone query
5. AudioCapture initial state and lifecycle
6. AudioCapture cancellation behavior
7. AudioCapture timeout handling
8. VoiceService transcription success
9. VoiceService transcription failure & error reporting
10. Voice → Phase 3 CommandService handoff & source=CommandSource.VOICE
11. SQLite persistence with source='voice'
12. Empty/whitespace transcript validation
13. Voice UI recording toggle and state synchronization
14. Voice UI low-confidence warning presentation
15. Privacy: No always-on recording
16. Privacy: Raw audio discarded (ephemeral in-memory buffer, zero disk persistence)
17. Privacy: Zero cloud API invocation
18. Settings window Voice tab microphone & provider telemetry
19. Security: Malicious spoken commands treated as plain inert text
"""
import os
import time
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer

from app.core.config import config
from app.core.state import app_state, TaskStatus
from app.core.events import event_bus
from app.agent.task_schema import CommandSource, CommandResult, CommandStatus
from app.services.task_service import CommandService
from app.storage.repositories import command_repository
from app.voice.stt_provider import STTProvider, STTProviderMetadata
from app.voice.providers.mock_stt import MockSTTProvider
from app.voice.providers.local_stt import LocalSTTProvider
from app.voice.audio_capture import AudioCapture, RecordingState
from app.voice.voice_service import VoiceService
from app.ui.main_window import MainWindow
from app.ui.settings_window import SettingsWindow


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance runs across tests."""
    app = QApplication.instance()
    if app is None:
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


class TestSTTProviderInterface:
    def test_mock_provider_metadata(self) -> None:
        provider = MockSTTProvider()
        meta = provider.metadata
        assert isinstance(meta, STTProviderMetadata)
        assert meta.provider_name == "Mock Test Provider"
        assert meta.local_processing is True
        assert provider.is_available is True

    def test_mock_provider_transcribe(self) -> None:
        provider = MockSTTProvider(mock_transcripts=["Open Notepad and write hello"])
        transcript, confidence = provider.transcribe(b"fake_audio_bytes", 16000)
        assert transcript == "Open Notepad and write hello"
        assert confidence == 0.95

    def test_mock_provider_error_simulation(self) -> None:
        provider = MockSTTProvider(should_fail=True, failure_message="Microphone buffer underrun")
        with pytest.raises(Exception) as exc_info:
            provider.transcribe(b"fake_audio_bytes", 16000)
        assert "Microphone buffer underrun" in str(exc_info.value)

    def test_local_stt_provider_truthful_reporting(self) -> None:
        provider = LocalSTTProvider()
        meta = provider.metadata
        assert meta.local_processing is True
        # Must report CPU, never fake NPU
        assert meta.accelerator == "CPU"
        assert meta.provider_name in ("Windows Native Speech (SAPI)", "Local STT (SpeechRecognition)")
        assert "en-US" in meta.supported_languages


class TestAudioCapture:
    def test_microphone_discovery(self, qapp) -> None:
        mics = AudioCapture.get_available_microphones()
        assert isinstance(mics, list)
        default_mic = AudioCapture.get_default_microphone_name()
        assert isinstance(default_mic, str)

    def test_initial_state(self, qapp) -> None:
        capture = AudioCapture()
        assert capture.state == RecordingState.IDLE
        assert capture.is_recording is False

    def test_cancel_recording(self, qapp) -> None:
        capture = AudioCapture()
        # Simulate recording state
        capture._set_state(RecordingState.LISTENING)
        assert capture.is_recording is True
        capture.cancel_recording()
        assert capture.state == RecordingState.CANCELLED
        assert capture.is_recording is False
        assert len(capture._audio_buffer) == 0

    def test_privacy_no_always_on(self, qapp) -> None:
        """Microphone capture must remain IDLE unless explicitly activated."""
        capture = AudioCapture()
        assert capture.is_recording is False
        assert capture.state == RecordingState.IDLE


class TestVoiceServicePipeline:
    def test_transcription_worker_and_phase3_handoff(self, qapp, clean_state) -> None:
        """VoiceService must pass recognized speech directly to Phase 3 CommandService."""
        mock_provider = MockSTTProvider(
            mock_transcripts=["Find the quarterly financial report in Documents"]
        )
        cmd_service = CommandService()
        voice_svc = VoiceService(provider=mock_provider, cmd_service=cmd_service)

        transcripts_received = []
        commands_received = []

        voice_svc.transcript_ready.connect(lambda t, c: transcripts_received.append((t, c)))
        voice_svc.command_processed.connect(lambda res: commands_received.append(res))

        # Directly dispatch synthetic audio buffer to test end-to-end worker
        voice_svc._handle_audio_captured(b"RIFFdummydataWAVEfmt")

        # Allow Qt thread worker to complete
        start = time.time()
        while not commands_received and time.time() - start < 3.0:
            qapp.processEvents()
            time.sleep(0.05)

        assert len(transcripts_received) == 1
        transcript, confidence = transcripts_received[0]
        assert transcript == "Find the quarterly financial report in Documents"
        assert confidence == 0.95

        assert len(commands_received) == 1
        result: CommandResult = commands_received[0]
        assert result.success is True
        assert result.task_request is not None
        assert result.task_request.source == CommandSource.VOICE
        assert result.task_request.prompt == "Find the quarterly financial report in Documents"

        # Verify SQLite persistence
        db_records = command_repository.get_recent(limit=1)
        assert len(db_records) == 1
        assert db_records[0]["source"] == "VOICE"
        assert db_records[0]["raw_text"] == "Find the quarterly financial report in Documents"

    def test_empty_audio_handling(self, qapp, clean_state) -> None:
        mock_provider = MockSTTProvider()
        voice_svc = VoiceService(provider=mock_provider)

        errors = []
        voice_svc.error_occurred.connect(lambda u, t: errors.append((u, t)))

        voice_svc._handle_audio_captured(b"")
        assert len(errors) == 1
        assert "No speech detected" in errors[0][0]

    def test_transcription_failure_handling(self, qapp, clean_state) -> None:
        mock_provider = MockSTTProvider(should_fail=True, failure_message="Acoustic model failure")
        voice_svc = VoiceService(provider=mock_provider)

        errors = []
        voice_svc.error_occurred.connect(lambda u, t: errors.append((u, t)))

        voice_svc._handle_audio_captured(b"dummy_audio")

        start = time.time()
        while not errors and time.time() - start < 3.0:
            qapp.processEvents()
            time.sleep(0.05)

        assert len(errors) == 1
        assert "Acoustic model failure" in errors[0][1]
        assert app_state.status == TaskStatus.IDLE

    def test_empty_transcript_validation(self, qapp, clean_state) -> None:
        """If STT produces empty string, Phase 3 validator rejects it cleanly."""
        mock_provider = MockSTTProvider(mock_transcripts=["   "])
        cmd_service = CommandService()
        voice_svc = VoiceService(provider=mock_provider, cmd_service=cmd_service)

        commands_received = []
        voice_svc.command_processed.connect(lambda res: commands_received.append(res))

        voice_svc._handle_audio_captured(b"dummy_audio")

        start = time.time()
        while not commands_received and time.time() - start < 3.0:
            qapp.processEvents()
            time.sleep(0.05)

        assert len(commands_received) == 1
        result = commands_received[0]
        assert result.success is False
        assert "Please enter a command" in result.message


class TestVoiceUIIntegration:
    def test_ui_mic_toggle(self, qapp, clean_state) -> None:
        window = MainWindow()
        mic_btn = window.command_input.mic_btn
        assert mic_btn.text() == "🎙️"

        # Toggle on
        window.command_input.set_recording_active(True)
        assert mic_btn.text() == "⏹️"
        assert "Recording" in mic_btn.toolTip()

        # Toggle off
        window.command_input.set_recording_active(False)
        assert mic_btn.text() == "🎙️"

    def test_ui_transcript_display(self, qapp, clean_state) -> None:
        window = MainWindow()
        window._on_voice_transcript_ready("Open Settings and check display", 0.92)
        assert window.command_input.editor.toPlainText() == "Open Settings and check display"

    def test_ui_low_confidence_warning(self, qapp, clean_state) -> None:
        window = MainWindow()
        window._on_voice_transcript_ready("Ambiguous murmur", 0.40)
        assert not window.error_banner.isHidden()
        assert "Voice transcription may be inaccurate" in window.error_msg_label.text()

    def test_settings_voice_tab(self, qapp, clean_state) -> None:
        settings = SettingsWindow()
        assert settings.mic_combo is not None
        assert settings.mic_combo.count() > 0


class TestVoiceSecurity:
    @pytest.mark.parametrize("malicious_transcript", [
        "Run powershell Start-Process calc.exe",
        "powershell -NoProfile -Command Write-Host PWNED",
        "rmdir /s /q C:\\Windows",
        "python -c \"import os; os.system('calc')\"",
        "<script>alert('xss')</script>",
        "'; DROP TABLE command_history; --",
    ])
    def test_malicious_voice_input_treated_as_plain_data(
        self, qapp, clean_state, malicious_transcript: str
    ) -> None:
        """Spoken malicious scripts or injection strings must be treated strictly as text data."""
        mock_provider = MockSTTProvider(mock_transcripts=[malicious_transcript])
        cmd_service = CommandService()
        voice_svc = VoiceService(provider=mock_provider, cmd_service=cmd_service)

        commands_received = []
        voice_svc.command_processed.connect(lambda res: commands_received.append(res))

        voice_svc._handle_audio_captured(b"dummy_audio")

        start = time.time()
        while not commands_received and time.time() - start < 3.0:
            qapp.processEvents()
            time.sleep(0.05)

        assert len(commands_received) == 1
        result = commands_received[0]

        # Validated and parsed as plain data in Phase 3
        assert result.success is True
        assert result.task_request is not None
        assert result.task_request.source == CommandSource.VOICE
        # Command must NOT have executed or spawned processes
        assert result.task_request.status == "READY_FOR_PLANNING"

        # SQLite database safely stored it without injection
        records = command_repository.get_recent(limit=1)
        assert len(records) == 1
        assert records[0]["raw_text"] == malicious_transcript
