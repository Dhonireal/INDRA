"""
VisionPilot Speech-to-Text (STT) Provider Abstraction.

Defines the extensible interface for local and fallback speech-to-text providers
with truthful capability and hardware accelerator reporting.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any


@dataclass
class STTProviderMetadata:
    """Truthful capability and accelerator telemetry for an STT provider."""
    provider_name: str
    model_name: str
    runtime: str
    accelerator: str = "CPU"
    local_processing: bool = True
    languages: list[str] = field(default_factory=lambda: ["en-US"])
    is_available: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def supported_languages(self) -> list[str]:
        return self.languages


class STTProvider(ABC):
    """Abstract Base Class for VisionPilot Speech-to-Text providers."""

    @property
    @abstractmethod
    def metadata(self) -> STTProviderMetadata:
        """Returns truthful provider metadata and hardware telemetry."""
        pass

    @property
    def is_available(self) -> bool:
        """Whether this STT provider is available and functional in current environment."""
        return self.metadata.is_available

    @abstractmethod
    def initialize(self) -> bool:
        """Initializes the underlying speech recognition engine/model. Returns True on success."""
        pass

    @abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> Tuple[str, Optional[float]]:
        """
        Transcribes raw PCM / WAV audio data into text.
        Returns a tuple of (transcript_text, optional_confidence_score).
        Raises VoiceError on failure.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Releases all model weights, audio buffers, and resources."""
        pass
