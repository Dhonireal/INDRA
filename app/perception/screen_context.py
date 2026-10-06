"""
VisionPilot Screen Context Helpers.

Provides lightweight querying of active application context, display metrics,
and window bounds for quick checks and telemetry.
"""
from typing import Optional, Dict, Any, List
from app.perception.models import WindowInfo, BoundingBox
from app.perception.ui_detector import LocalUIAutomationProvider
from app.perception.screen_capture import LocalScreenCaptureProvider


class ScreenContext:
    """Utility class providing instant access to window and screen properties."""

    def __init__(self) -> None:
        self.uia_provider = LocalUIAutomationProvider()
        self.capture_provider = LocalScreenCaptureProvider()

    def get_active_window(self) -> Optional[WindowInfo]:
        """Returns the active window if any is detected."""
        return self.uia_provider.get_active_window()

    def get_visible_windows(self) -> List[WindowInfo]:
        """Returns all visible desktop windows."""
        return self.uia_provider.enumerate_windows()

    def get_display_metrics(self) -> Dict[str, Any]:
        """Returns display count, primary dimensions, and DPI scale."""
        return self.capture_provider.get_display_info()
