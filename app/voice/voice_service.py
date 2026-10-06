"""
VisionPilot Voice Service.

Coordinates audio capture with Speech-to-Text transcription.
Hands recognized transcripts directly to the Phase 3 CommandService with source=CommandSource.VOICE.
Strictly reuses Phase 3 validation, normalization, and task lifecycle.
"""
from typing import Optional, Tuple, Dict, Any
import time
from PySide6.QtCore import QObject, Signal, Slot, QThread

from app.core.logger import logger
from app.core.state import app_state, TaskStatus
from app.core.exceptions import VoiceError
from app.agent.task_schema import CommandSource, CommandResult
from app.services.task_service import command_service, CommandService
from app.voice.stt_provider import STTProvider
from app.voice.providers.local_stt import LocalSTTProvider
from app.voice.audio_capture import AudioCapture, RecordingState


class VoiceTranscriptionWorker(QObject):
    """Background worker for transcribing audio off the main Qt UI thread."""
    finished = Signal(str, object, float)  # transcript, confidence, duration_sec
    failed = Signal(str, str)  # user_msg, tech_details

    def __init__(self, provider: STTProvider, audio_bytes: bytes, sample_rate: int = 16000) -> None:
        super().__init__()
        self.provider = provider
        self.audio_bytes = audio_bytes
        self.sample_rate = sample_rate

    @Slot()
    def run(self) -> None:
        start_time = time.perf_counter()
        try:
            transcript, confidence = self.provider.transcribe(self.audio_bytes, self.sample_rate)
            duration = time.perf_counter() - start_time
            self.finished.emit(transcript, confidence, duration)
        except VoiceError as ve:
            self.failed.emit(ve.get_user_friendly_message(), str(ve))
        except Exception as e:
            logger.exception(f"Unexpected error during transcription: {e}")
            self.failed.emit("Speech recognition encountered an unexpected issue.", str(e))


class VoiceService(QObject):
    """Main voice interaction service."""

    transcript_ready = Signal(str, object)  # transcript, confidence
    command_processed = Signal(object)      # CommandResult from Phase 3
    state_changed = Signal(str)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        provider: Optional[STTProvider] = None,
        cmd_service: Optional[CommandService] = None,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.provider = provider or LocalSTTProvider()
        self.cmd_service = cmd_service or command_service
        self.audio_capture = AudioCapture(parent=self)

        # Worker thread handle
        self._thread: Optional[QThread] = None
        self._worker: Optional[VoiceTranscriptionWorker] = None

        self._wire_signals()

    def _wire_signals(self) -> None:
        self.audio_capture.state_changed.connect(self._handle_audio_state_changed)
        self.audio_capture.audio_captured.connect(self._handle_audio_captured)
        self.audio_capture.error_occurred.connect(self.error_occurred.emit)

    def set_provider(self, provider: STTProvider) -> None:
        """Sets active STT provider (e.g. for testing with MockSTTProvider)."""
        self.provider = provider
        logger.info(f"VoiceService provider set to: {provider.metadata.provider_name}")

    def start_listening(self) -> bool:
        """Activates microphone recording on demand."""
        logger.info("VoiceService starting listening...")
        app_state.update_status(TaskStatus.LISTENING, "Listening for spoken command...")
        success = self.audio_capture.start_recording()
        if not success:
            app_state.reset()
        return success

    def stop_listening(self) -> None:
        """Stops recording and triggers background transcription."""
        logger.info("VoiceService stopping listening...")
        app_state.update_status(TaskStatus.ANALYZING, "Transcribing speech...")
        self.audio_capture.stop_recording()

    def cancel(self) -> None:
        """Cancels recording and aborts any active transcription."""
        logger.info("VoiceService cancelling voice pipeline...")
        self.audio_capture.cancel_recording()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
        app_state.reset()
        self.state_changed.emit("CANCELLED")

    def _handle_audio_state_changed(self, state_str: str) -> None:
        self.state_changed.emit(state_str)

    def _handle_audio_captured(self, wav_bytes: bytes) -> None:
        """Dispatches audio to background worker for transcription."""
        if not wav_bytes or len(wav_bytes) == 0:
            logger.warning("Empty audio captured. Resetting voice state.")
            app_state.reset()
            self.error_occurred.emit("No speech detected. Please speak into your microphone.", "Empty audio buffer")
            return

        # Initialize background worker thread
        self._thread = QThread()
        self._worker = VoiceTranscriptionWorker(self.provider, wav_bytes, self.audio_capture.sample_rate)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_transcription_finished)
        self._worker.failed.connect(self._on_transcription_failed)

        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def _on_transcription_finished(self, transcript: str, confidence: Optional[float], duration_sec: float) -> None:
        """Handles successful transcription from worker."""
        logger.info(
            f"Transcription completed in {duration_sec:.2f}s | "
            f"Transcript: '{transcript}' (Confidence: {confidence})"
        )
        self.transcript_ready.emit(transcript, confidence)

        # Hand off transcript directly to Phase 3 CommandService!
        result: CommandResult = self.cmd_service.process_command(
            raw_text=transcript,
            source=CommandSource.VOICE
        )
        self.command_processed.emit(result)

    def _on_transcription_failed(self, user_msg: str, tech_details: str) -> None:
        """Handles transcription failure."""
        logger.warning(f"Voice transcription failed: {user_msg} | Details: {tech_details}")
        app_state.reset()
        self.error_occurred.emit(user_msg, tech_details)


# Global VoiceService instance
voice_service = VoiceService()
