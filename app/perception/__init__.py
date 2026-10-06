"""
VisionPilot Perception Subsystem.

Provides screen capture, active window detection, Windows UI Automation (UIA)
accessibility tree inspection, native Windows Media OCR, fusion, and visual grounding.

READ-ONLY: Perception observes and structures desktop state; it never initiates computer actions.
"""
from app.perception.models import (
    BoundingBox, UIElement, OCRTextRegion, WindowInfo,
    CaptureScope, PerceptionRequest, GroundingCandidate, ScreenState
)
from app.perception.screen_capture import (
    ScreenCaptureProvider, LocalScreenCaptureProvider, MockScreenCaptureProvider
)
from app.perception.ui_detector import (
    UIAutomationProvider, LocalUIAutomationProvider, MockUIAutomationProvider
)
from app.perception.ocr.ocr_provider import OCRProvider, MockOCRProvider
from app.perception.ocr.local_ocr import LocalOCRProvider
from app.perception.grounding import PerceptionFuser, VisualGrounder
from app.perception.perception_engine import PerceptionEngine, perception_engine

__all__ = [
    "BoundingBox",
    "UIElement",
    "OCRTextRegion",
    "WindowInfo",
    "CaptureScope",
    "PerceptionRequest",
    "GroundingCandidate",
    "ScreenState",
    "ScreenCaptureProvider",
    "LocalScreenCaptureProvider",
    "MockScreenCaptureProvider",
    "UIAutomationProvider",
    "LocalUIAutomationProvider",
    "MockUIAutomationProvider",
    "OCRProvider",
    "MockOCRProvider",
    "LocalOCRProvider",
    "PerceptionFuser",
    "VisualGrounder",
    "PerceptionEngine",
    "perception_engine"
]
