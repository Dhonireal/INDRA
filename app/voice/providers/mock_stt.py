"""
VisionPilot Mock STT Provider for Testing.

Strictly used for unit, integration, and security testing.
NEVER used automatically in production.
"""
from typing import Optional, Tuple
from app.core.exceptions import VoiceError
from app.voice.stt_provider import STTProvider, STTProviderMetadata


class MockSTTProvider(STTProvider):
    """Deterministic mock speech-to-text provider for automated testing."""

    def __init__(
        self,
        mock_transcript: str = "Find the latest PDF in Downloads and move it to Research",
        mock_confidence: float = 0.95,
        should_fail: bool = False,
        error_message: str = "Simulated microphone capture failure",
        mock_transcripts: Optional[list[str]] = None,
        failure_message: Optional[str] = None
    ) -> None:
        if mock_transcripts:
            self.mock_transcripts = list(mock_transcripts)
            self.mock_transcript = self.mock_transcripts[0]
        else:
            self.mock_transcripts = [mock_transcript]
            self.mock_transcript = mock_transcript

        self._transcript_idx = 0
        self.mock_confidence = mock_confidence
        self.should_fail = should_fail
        self.error_message = failure_message or error_message
        self._initialized = False

        self._metadata = STTProviderMetadata(
            provider_name="Mock Test Provider",
            model_name="MockSTTModel",
            runtime="In-Memory Test Mock",
            accelerator="None (Simulation)",
            local_processing=True,
            languages=["en-US"],
            is_available=True
        )

    @property
    def metadata(self) -> STTProviderMetadata:
        return self._metadata

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Tuple[str, Optional[float]]:
        if not self._initialized:
            self.initialize()

        if self.should_fail:
            raise VoiceError(self.error_message, "Speech recognition failed during test simulation.")

        if not audio_data or len(audio_data) == 0:
            raise VoiceError("Audio data is empty.", "No speech detected.")

        transcript = self.mock_transcripts[self._transcript_idx % len(self.mock_transcripts)]
        self._transcript_idx += 1
        return transcript, self.mock_confidence

    def cleanup(self) -> None:
        self._initialized = False
