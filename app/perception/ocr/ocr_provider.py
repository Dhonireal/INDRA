"""
VisionPilot Optical Character Recognition (OCR) Provider Abstraction.

Defines the interface for local-first, privacy-compliant OCR engines.
No cloud OCR services or external data transmissions are permitted.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from app.perception.models import OCRTextRegion, BoundingBox


class OCRProvider(ABC):
    """Abstract Base Class for OCR providers."""

    @property
    @abstractmethod
    def metadata(self) -> Dict[str, Any]:
        """Returns truthful OCR provider metadata and accelerator telemetry."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this OCR engine is operational in the current environment."""
        pass

    @abstractmethod
    def recognize(self, image_bytes: bytes) -> List[OCRTextRegion]:
        """
        Extracts structured text regions and bounding boxes from image bytes.
        Returns a list of OCRTextRegion objects.
        """
        pass


class MockOCRProvider(OCRProvider):
    """Deterministic mock OCR provider for unit and security tests."""

    def __init__(
        self,
        mock_regions: Optional[List[OCRTextRegion]] = None,
        should_fail: bool = False
    ) -> None:
        self.should_fail = should_fail
        self.mock_regions = mock_regions or [
            OCRTextRegion(
                text="Download",
                bounding_box=BoundingBox(105, 155, 255, 195),
                confidence=0.98,
                language="en-US"
            ),
            OCRTextRegion(
                text="Cancel",
                bounding_box=BoundingBox(285, 155, 415, 195),
                confidence=0.95,
                language="en-US"
            ),
            OCRTextRegion(
                text="Research Document",
                bounding_box=BoundingBox(50, 80, 320, 110),
                confidence=0.92,
                language="en-US"
            )
        ]

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "provider_name": "Mock OCR Provider",
            "runtime": "In-Memory Test Mock",
            "accelerator": "None (Simulation)",
            "local_processing": True,
            "language": "en-US"
        }

    @property
    def is_available(self) -> bool:
        return True

    def recognize(self, image_bytes: bytes) -> List[OCRTextRegion]:
        if self.should_fail:
            raise RuntimeError("Simulated OCR failure.")
        return list(self.mock_regions)
