"""
VisionPilot Vision-Language Model (VLM) Provider Abstraction.

Defines the interface for future multimodal screen understanding.
In Phase 5, this interface serves as a contract placeholder.
NO large VLM is downloaded or executed in Phase 5.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class VisionProvider(ABC):
    """Abstract interface for optional multimodal vision models (Phase 6+)."""

    @property
    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Returns provider metadata, model name, and accelerator telemetry."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether a local or configured VLM is loaded and available."""
        pass

    @abstractmethod
    def analyze(self, image_bytes: bytes, prompt: str) -> str:
        """
        Analyzes a screenshot with a natural-language visual query.
        (Reserved for Phase 6+ AI Planning).
        """
        pass
