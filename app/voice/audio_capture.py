"""
VisionPilot Audio Capture Subsystem.

Discovers audio input devices and manages microphone recording using PySide6 QtMultimedia.
Operates on-demand only (NO always-on listening, NO continuous background recording).
Enforces bounded recording duration, clean cancellation, and safe resource cleanup.
"""
from typing import List, Optional, Dict, Any
from enum import Enum
import io
import wave
from PySide6.QtCore import QObject, Signal, QTimer, QByteArray, QIODevice
from PySide6.QtMultimedia import (
    QMediaDevices, QAudioInput, QAudioSource,
    QAudioFormat, QAudioDevice
)
from app.core.logger import logger
from app.core.exceptions import VoiceError


class RecordingState(str, Enum):
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class AudioCapture(QObject):
    """Manages microphone selection and bounded audio recording."""

    state_changed = Signal(str)
    recording_started = Signal()
    recording_stopped = Signal()
    audio_captured = Signal(bytes)
    error_occurred = Signal(str, str)  # user_msg, tech_details

    def __init__(
        self,
        sample_rate: int = 16000,
        max_duration_seconds: int = 15,
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self.sample_rate = sample_rate
        self.max_duration_seconds = max_duration_seconds
        self.state = RecordingState.IDLE

        self._audio_source: Optional[QAudioSource] = None
        self._audio_input: Optional[QAudioInput] = None
        self._io_device: Optional[QIODevice] = None
        self._audio_buffer = bytearray()
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self._handle_timeout)
        self._selected_device_name: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        """Whether audio is actively being captured."""
        return self.state == RecordingState.LISTENING

    @staticmethod
    def get_available_microphones() -> List[str]:
        """Returns list of descriptions for all detected audio input devices."""
        try:
            inputs = QMediaDevices.audioInputs()
            return [dev.description() for dev in inputs if dev.description()]
        except Exception as e:
            logger.warning(f"Error enumerating audio inputs: {e}")
            return []

    @staticmethod
    def get_default_microphone_name() -> str:
        """Returns the description of the default system audio input."""
        try:
            default_dev = QMediaDevices.defaultAudioInput()
            return default_dev.description() or "Default System Microphone"
        except Exception as e:
            logger.warning(f"Error querying default microphone: {e}")
            return "Default System Microphone"

    def set_device(self, device_name: str) -> bool:
        """Selects a specific input device by name."""
        try:
            for dev in QMediaDevices.audioInputs():
                if dev.description() == device_name:
                    self._selected_device_name = device_name
                    logger.info(f"Selected audio input device: {device_name}")
                    return True
        except Exception as e:
            logger.warning(f"Error selecting audio device {device_name}: {e}")
        return False

    def _get_audio_device(self) -> QAudioDevice:
        """Resolves the active QAudioDevice."""
        if self._selected_device_name:
            for dev in QMediaDevices.audioInputs():
                if dev.description() == self._selected_device_name:
                    return dev
        return QMediaDevices.defaultAudioInput()

    def start_recording(self) -> bool:
        """Starts recording from the selected microphone."""
        if self.state == RecordingState.LISTENING:
            logger.warning("Recording already in progress.")
            return False

        self._set_state(RecordingState.INITIALIZING)
        device = self._get_audio_device()

        if device.isNull():
            err_msg = "No audio input device detected."
            user_msg = "No microphone was detected. Please connect an audio input device."
            logger.error(err_msg)
            self._set_state(RecordingState.ERROR)
            self.error_occurred.emit(user_msg, err_msg)
            return False

        try:
            # Configure 16-bit Mono PCM
            format = QAudioFormat()
            format.setSampleRate(self.sample_rate)
            format.setChannelCount(1)
            format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            if not device.isFormatSupported(format):
                format = device.preferredFormat()

            self._audio_input = QAudioInput(device, self)
            self._audio_source = QAudioSource(device, format, self)
            self._audio_buffer = bytearray()

            self._io_device = self._audio_source.start()
            if not self._io_device:
                raise VoiceError("QAudioSource failed to start IO device.")

            self._io_device.readyRead.connect(self._on_audio_data_ready)

            # Start bounded safety timeout
            self._timeout_timer.start(self.max_duration_seconds * 1000)

            self._set_state(RecordingState.LISTENING)
            self.recording_started.emit()
            logger.info(f"Audio recording started on '{device.description()}' (Max: {self.max_duration_seconds}s)")
            return True

        except Exception as e:
            err_msg = f"Failed to start audio recording: {e}"
            user_msg = "Could not access microphone. Please check your Windows microphone permissions."
            logger.error(err_msg)
            self.cleanup()
            self._set_state(RecordingState.ERROR)
            self.error_occurred.emit(user_msg, err_msg)
            return False

    def _on_audio_data_ready(self) -> None:
        """Callback reading chunks from the audio IO device."""
        if self._io_device and self.state == RecordingState.LISTENING:
            data = self._io_device.readAll()
            if data:
                self._audio_buffer.extend(data.data())

    def stop_recording(self) -> bytes:
        """Stops active recording and returns packaged WAV audio bytes."""
        if self.state != RecordingState.LISTENING:
            return b""

        self._timeout_timer.stop()
        self._set_state(RecordingState.PROCESSING)

        if self._audio_source:
            self._audio_source.stop()

        raw_pcm = bytes(self._audio_buffer)
        wav_bytes = self._package_wav(raw_pcm)

        self.cleanup()
        self._set_state(RecordingState.IDLE)
        self.recording_stopped.emit()
        self.audio_captured.emit(wav_bytes)
        logger.info(f"Audio recording stopped. Captured {len(raw_pcm)} bytes PCM.")
        return wav_bytes

    def cancel_recording(self) -> None:
        """Cancels current recording and discards audio buffer."""
        logger.info("Audio recording cancelled by user.")
        self._timeout_timer.stop()
        if self._audio_source:
            self._audio_source.stop()
        self.cleanup()
        self._set_state(RecordingState.CANCELLED)
        self.recording_stopped.emit()

    def _handle_timeout(self) -> None:
        """Fires when recording duration hits maximum bounded duration."""
        logger.info(f"Audio recording reached maximum duration ({self.max_duration_seconds}s). Stopping automatically.")
        self.stop_recording()

    def _package_wav(self, raw_pcm: bytes) -> bytes:
        """Encapsulates 16-bit mono PCM into standard WAV container bytes."""
        if not raw_pcm:
            return b""
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(raw_pcm)
        return wav_io.getvalue()

    def _set_state(self, new_state: RecordingState) -> None:
        self.state = new_state
        self.state_changed.emit(new_state.value)

    def cleanup(self) -> None:
        """Releases audio device handles and clears buffer."""
        if self._audio_source:
            try:
                self._audio_source.stop()
            except Exception:
                pass
            self._audio_source = None

        self._audio_input = None
        self._io_device = None
        self._audio_buffer.clear()
