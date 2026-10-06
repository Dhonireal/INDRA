"""
VisionPilot Dormant Local Vision Provider.

Placeholder for future small vision-language model integration (Phase 6+).
Strictly preserves Phase 5 boundaries: No VLM downloads, no external API calls.
"""
from typing import Dict, Any
from app.perception.vision.vision_provider import VisionProvider


class LocalVisionProvider(VisionProvider):
    """Local VLM Provider placeholder."""

    def __init__(self) -> None:
        self._available = False

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "provider_name": "Local VLM (Unloaded)",
            "model_name": "None (Dormant in Phase 5)",
            "runtime": "None",
            "accelerator": "None",
            "is_available": False,
            "status": "Dormant (Scheduled for Phase 6 AI Planning)"
        }

    @property
    def is_available(self) -> bool:
        return False

    def analyze(self, image_bytes: bytes, prompt: str) -> str:
        raise NotImplementedError(
            "VLM visual reasoning is reserved for Phase 6 (AI Task Planning). "
            "Phase 5 operates purely via UI Automation + OCR perception."
        )
