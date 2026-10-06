"""
VisionPilot Perception Engine.

Master orchestrator for on-demand screen inspection, active window telemetry,
UI Automation extraction, native Windows Media OCR, fusion, and visual grounding.

CRITICAL ARCHITECTURE RULE:
Perception is strictly READ-ONLY. The perception engine observes desktop state
and generates structured data. It never generates mouse clicks, keystrokes, or computer actions.
"""
from typing import Optional, List, Dict, Any, Tuple
import time
import uuid

from app.core.config import config
from app.core.logger import logger
from app.core.events import event_bus, ScreenCapturedEvent, PerceptionCompletedEvent
from app.core.exceptions import PerceptionError
from app.perception.models import (
    ScreenState, PerceptionRequest, CaptureScope, UIElement,
    OCRTextRegion, WindowInfo, GroundingCandidate, BoundingBox
)
from app.perception.screen_capture import ScreenCaptureProvider, LocalScreenCaptureProvider
from app.perception.ui_detector import UIAutomationProvider, LocalUIAutomationProvider
from app.perception.ocr.ocr_provider import OCRProvider
from app.perception.ocr.local_ocr import LocalOCRProvider
from app.perception.grounding import PerceptionFuser, VisualGrounder


class PerceptionEngine:
    """Coordinates on-demand screen perception and visual grounding."""

    def __init__(
        self,
        capture_provider: Optional[ScreenCaptureProvider] = None,
        uia_provider: Optional[UIAutomationProvider] = None,
        ocr_provider: Optional[OCRProvider] = None,
        fuser: Optional[PerceptionFuser] = None,
        grounder: Optional[VisualGrounder] = None
    ) -> None:
        self.capture_provider = capture_provider or LocalScreenCaptureProvider()
        self.uia_provider = uia_provider or LocalUIAutomationProvider()
        self.ocr_provider = ocr_provider or LocalOCRProvider()
        self.fuser = fuser or PerceptionFuser()
        self.grounder = grounder or VisualGrounder(self.fuser)

        # Short-lived snapshot cache
        self._cached_state: Optional[ScreenState] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl = config.perception.cache_ttl_seconds

    def perceive(self, request: Optional[PerceptionRequest] = None) -> ScreenState:
        """
        Executes a complete on-demand perception cycle.
        Returns a structured ScreenState snapshot.
        """
        req = request or PerceptionRequest()
        start_time = time.perf_counter()
        snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
        sources_used: List[str] = []

        # Check short-lived cache
        now = time.time()
        if (
            self._cached_state and
            (now - self._cache_timestamp < self._cache_ttl) and
            req.scope == CaptureScope.ACTIVE_WINDOW
        ):
            logger.debug("Returning short-lived cached ScreenState snapshot.")
            return self._cached_state

        logger.info(f"Initiating on-demand perception snapshot [{snapshot_id}] with scope: {req.scope.value}")

        # 1. Screen Dimensions & Display Telemetry
        display_info = self.capture_provider.get_display_info()
        screen_dims = display_info.get("primary_dimensions", (1920, 1080))
        dpi_scale = display_info.get("primary_dpi_scale", 1.0)
        display_count = display_info.get("display_count", 1)

        # 2. Window Telemetry & Active Window Detection
        active_window: Optional[WindowInfo] = None
        all_windows: List[WindowInfo] = []

        if req.include_ui_elements:
            try:
                active_window = self.uia_provider.get_active_window()
                all_windows = self.uia_provider.enumerate_windows()
                sources_used.append("Win32/UIA")
            except Exception as e:
                logger.warning(f"Error querying window telemetry: {e}")

        # Target HWND resolution
        target_hwnd = req.target_window_hwnd
        if not target_hwnd and req.scope == CaptureScope.ACTIVE_WINDOW and active_window:
            target_hwnd = active_window.hwnd

        # 3. UI Element Tree Extraction (UIA)
        ui_elements: List[UIElement] = []
        if req.include_ui_elements:
            try:
                ui_elements = self.uia_provider.extract_elements(
                    target_hwnd=target_hwnd,
                    timeout_seconds=min(3.0, req.timeout_seconds)
                )
            except Exception as e:
                logger.warning(f"UIA element extraction error: {e}")

        # 4. Lazy OCR Decision
        # If UIA provided sufficient elements and lazy_ocr is enabled, we can skip expensive OCR
        run_ocr = req.include_ocr and self.ocr_provider.is_available
        if run_ocr and config.perception.lazy_ocr and len(ui_elements) >= 15:
            # We already have a rich accessibility tree for standard applications
            # Only run OCR if explicitly requested or if UIA was sparse (< 15 controls)
            run_ocr = False
            logger.debug(f"Lazy OCR active: UIA returned {len(ui_elements)} controls; skipping OCR.")

        # 5. Screen Capture (if OCR requested or screenshot explicitly enabled)
        png_bytes: Optional[bytes] = None
        ocr_regions: List[OCRTextRegion] = []

        if run_ocr or req.include_screenshot:
            try:
                png_bytes, actual_dims, capture_dpi = self.capture_provider.capture(
                    scope=req.scope,
                    target_hwnd=target_hwnd
                )
                screen_dims = actual_dims
                dpi_scale = capture_dpi
                sources_used.append("ScreenCapture")

                event_bus.publish(ScreenCapturedEvent(
                    capture_id=snapshot_id,
                    width=actual_dims[0],
                    height=actual_dims[1],
                    scope=req.scope.value
                ))
            except Exception as e:
                logger.warning(f"Screen capture failed: {e}")

        # 6. OCR Execution
        if run_ocr and png_bytes:
            try:
                ocr_regions = self.ocr_provider.recognize(png_bytes)
                if ocr_regions:
                    sources_used.append("OCR")
            except Exception as e:
                logger.warning(f"OCR execution failed: {e}")

        # 7. UIA + OCR Fusion & Deduplication
        fused_elements: List[UIElement] = []
        if ui_elements or ocr_regions:
            fused_elements = self.fuser.fuse(ui_elements, ocr_regions)
        else:
            fused_elements = []

        # 8. Assemble ScreenState Snapshot
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        screen_state = ScreenState(
            snapshot_id=snapshot_id,
            active_window=active_window,
            windows=all_windows,
            ui_elements=ui_elements,
            ocr_regions=ocr_regions,
            fused_elements=fused_elements,
            screen_dimensions=screen_dims,
            display_count=display_count,
            dpi_scale=dpi_scale,
            sources=sources_used,
            metadata={
                "duration_ms": round(duration_ms, 2),
                "scope": req.scope.value,
                "lazy_ocr_triggered": not run_ocr and req.include_ocr,
                "privacy_mode": req.privacy_mode
            },
            # Only store screenshot bytes in memory if explicitly requested (ephemeral)
            screenshot_bytes=png_bytes if (req.include_screenshot and config.perception.store_screenshots) else None
        )

        # Update cache
        self._cached_state = screen_state
        self._cache_timestamp = time.time()

        # Publish completion event
        event_bus.publish(PerceptionCompletedEvent(
            snapshot_id=snapshot_id,
            element_count=len(fused_elements),
            ocr_region_count=len(ocr_regions),
            active_window_title=active_window.title if active_window else "None",
            duration_ms=round(duration_ms, 2),
            sources=sources_used
        ))

        logger.info(
            f"Perception snapshot [{snapshot_id}] completed in {duration_ms:.1f}ms | "
            f"Active: '{active_window.title if active_window else 'None'}' | "
            f"Elements: {len(fused_elements)} (UIA: {len(ui_elements)}, OCR: {len(ocr_regions)})"
        )
        return screen_state

    def ground(
        self,
        query: str,
        screen_state: Optional[ScreenState] = None,
        preferred_role: Optional[str] = None
    ) -> List[GroundingCandidate]:
        """
        Locates UI elements matching a query within an existing or fresh ScreenState.
        """
        state = screen_state or self.perceive()
        return self.grounder.ground(query, state, preferred_role=preferred_role)


# Global PerceptionEngine singleton instance
perception_engine = PerceptionEngine()
