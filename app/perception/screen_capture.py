"""
VisionPilot Screen Capture Subsystem.

Provides on-demand desktop and window capture using PySide6 QtMultimedia / QScreen
with graceful PIL ImageGrab fallback.

Privacy-First:
- Operates ON-DEMAND only (NO background surveillance, NO continuous capture)
- Ephemeral in-memory image buffers (discarded immediately after processing)
- Zero cloud transmission
"""
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any, List
import io
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QScreen, QImage, QPixmap
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt

from app.core.logger import logger
from app.core.exceptions import PerceptionError
from app.perception.models import CaptureScope, BoundingBox


class ScreenCaptureProvider(ABC):
    """Abstract interface for desktop and window screen capture."""

    @abstractmethod
    def capture(
        self,
        scope: CaptureScope = CaptureScope.ACTIVE_WINDOW,
        target_hwnd: Optional[int] = None
    ) -> Tuple[bytes, Tuple[int, int], float]:
        """
        Captures the screen or window.
        Returns:
            (png_image_bytes, (width, height), dpi_scale)
        """
        pass

    @abstractmethod
    def get_display_info(self) -> Dict[str, Any]:
        """Returns monitor geometry, DPI, and display metrics."""
        pass


class LocalScreenCaptureProvider(ScreenCaptureProvider):
    """On-demand screen capture provider utilizing Qt6 QScreen and Win32."""

    def __init__(self) -> None:
        self._ensure_qapp()

    def _ensure_qapp(self) -> None:
        if not QApplication.instance():
            # In headless environments, initialize offscreen platform
            self._qapp = QApplication(["-platform", "offscreen"])

    def get_display_info(self) -> Dict[str, Any]:
        """Queries connected displays, resolution, and DPI scaling."""
        screens = QGuiApplication.screens()
        display_info: List[Dict[str, Any]] = []

        primary_w, primary_h = 1920, 1080
        primary_dpr = 1.0

        for i, screen in enumerate(screens):
            geo = screen.geometry()
            dpr = screen.devicePixelRatio()
            logical_dpi = screen.logicalDotsPerInch()
            info = {
                "index": i,
                "name": screen.name(),
                "logical_width": geo.width(),
                "logical_height": geo.height(),
                "device_pixel_ratio": dpr,
                "logical_dpi": logical_dpi,
                "is_primary": screen == QGuiApplication.primaryScreen()
            }
            display_info.append(info)
            if info["is_primary"]:
                primary_w = int(geo.width() * dpr)
                primary_h = int(geo.height() * dpr)
                primary_dpr = dpr

        return {
            "display_count": len(screens),
            "primary_dimensions": (primary_w, primary_h),
            "primary_dpi_scale": primary_dpr,
            "displays": display_info
        }

    def capture(
        self,
        scope: CaptureScope = CaptureScope.ACTIVE_WINDOW,
        target_hwnd: Optional[int] = None
    ) -> Tuple[bytes, Tuple[int, int], float]:
        """
        Captures requested desktop bounds into in-memory PNG bytes.
        Does NOT persist screenshots to disk.
        """
        screen = QGuiApplication.primaryScreen()
        if not screen:
            logger.error("No QScreen detected for screen capture.")
            raise PerceptionError("Screen capture failed: No active display detected.")

        try:
            dpr = screen.devicePixelRatio()
            hwnd_to_grab = target_hwnd if (target_hwnd and scope == CaptureScope.SPECIFIC_WINDOW) else 0

            # Grab pixmap directly via Qt
            pixmap = screen.grabWindow(hwnd_to_grab)
            if pixmap.isNull():
                logger.warning(f"QScreen.grabWindow({hwnd_to_grab}) returned null pixmap. Trying PIL fallback.")
                return self._capture_pil_fallback()

            image: QImage = pixmap.toImage()
            width, height = image.width(), image.height()

            # Encode to in-memory PNG bytes
            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            image.save(buffer, "PNG")
            png_bytes = bytes(byte_array.data())

            # Explicit cleanup
            buffer.close()
            del pixmap
            del image

            logger.debug(f"Screen capture completed ({width}x{height}, DPI Scale={dpr})")
            return png_bytes, (width, height), dpr

        except Exception as e:
            logger.warning(f"Error during Qt screen capture: {e}. Attempting fallback.")
            return self._capture_pil_fallback()

    def _capture_pil_fallback(self) -> Tuple[bytes, Tuple[int, int], float]:
        """Fallback capture via Pillow ImageGrab."""
        try:
            from PIL import ImageGrab
            pil_img = ImageGrab.grab()
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
            w, h = pil_img.size
            return png_bytes, (w, h), 1.0
        except Exception as e:
            logger.error(f"Pillow ImageGrab fallback failed: {e}")
            raise PerceptionError("Failed to capture desktop screen.", str(e))


class MockScreenCaptureProvider(ScreenCaptureProvider):
    """Deterministic mock provider returning synthetic test images for unit tests."""

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        dpi_scale: float = 1.0,
        synthetic_text: Optional[str] = None
    ) -> None:
        self.width = width
        self.height = height
        self.dpi_scale = dpi_scale
        self.synthetic_text = synthetic_text

    def get_display_info(self) -> Dict[str, Any]:
        return {
            "display_count": 1,
            "primary_dimensions": (self.width, self.height),
            "primary_dpi_scale": self.dpi_scale,
            "displays": [{
                "index": 0,
                "name": "MockDisplay",
                "logical_width": int(self.width / self.dpi_scale),
                "logical_height": int(self.height / self.dpi_scale),
                "device_pixel_ratio": self.dpi_scale,
                "logical_dpi": 96.0 * self.dpi_scale,
                "is_primary": True
            }]
        }

    def capture(
        self,
        scope: CaptureScope = CaptureScope.ACTIVE_WINDOW,
        target_hwnd: Optional[int] = None
    ) -> Tuple[bytes, Tuple[int, int], float]:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (self.width, self.height), color="#F8FAFC")
        draw = ImageDraw.Draw(img)

        # Draw a synthetic title bar and button
        draw.rectangle([(0, 0), (self.width, 40)], fill="#1E293B")
        draw.text((20, 10), "Test Mock Application", fill="#FFFFFF")

        # Draw simulated button
        btn_box = (100, 150, 260, 200)
        draw.rectangle(btn_box, fill="#0284C7", outline="#0369A1", width=2)

        if self.synthetic_text:
            draw.text((120, 165), self.synthetic_text, fill="#FFFFFF")
        else:
            draw.text((120, 165), "Download", fill="#FFFFFF")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), (self.width, self.height), self.dpi_scale
