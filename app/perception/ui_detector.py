"""
VisionPilot Windows UI Automation (UIA) Provider.

Extracts structured UI accessibility elements, control types, bounding boxes,
and active window telemetry from the Windows desktop using native UI Automation.

Privacy & Security:
- READ-ONLY: Never generates input events, clicks, or keystrokes
- Credential Protection: Password and credential fields are strictly redacted
"""
from abc import ABC, abstractmethod
import ctypes
from ctypes import wintypes
import time
from typing import List, Optional, Tuple, Dict, Any

from app.core.logger import logger
from app.core.exceptions import PerceptionError
from app.perception.models import UIElement, BoundingBox, WindowInfo

try:
    import uiautomation as auto
    import win32gui
    import win32process
    HAS_NATIVE_UIA = True
except ImportError:
    HAS_NATIVE_UIA = False


class UIAutomationProvider(ABC):
    """Abstract interface for desktop accessibility inspection."""

    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """Returns metadata for the currently active foreground window."""
        pass

    @abstractmethod
    def enumerate_windows(self) -> List[WindowInfo]:
        """Enumerates all top-level visible desktop windows."""
        pass

    @abstractmethod
    def extract_elements(
        self,
        target_hwnd: Optional[int] = None,
        max_depth: int = 4,
        timeout_seconds: float = 3.0
    ) -> List[UIElement]:
        """
        Extracts structured UI elements from a window or the entire desktop.
        """
        pass


class LocalUIAutomationProvider(UIAutomationProvider):
    """Native Windows UI Automation provider using uiautomation and win32gui."""

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._setup_ctypes()

    def _setup_ctypes(self) -> None:
        try:
            self._user32.GetForegroundWindow.restype = wintypes.HWND
            self._user32.OpenDesktopW.restype = wintypes.HDESK
            self._user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self._user32.SetThreadDesktop.argtypes = [wintypes.HDESK]
            self._user32.SetThreadDesktop.restype = wintypes.BOOL
        except Exception:
            pass

    def _ensure_desktop_access(self) -> None:
        """Ensures the calling thread can access the interactive user desktop."""
        try:
            h_desk = self._user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_desk:
                self._user32.SetThreadDesktop(h_desk)
        except Exception:
            pass

    def get_active_window(self) -> Optional[WindowInfo]:
        """Retrieves active foreground window info."""
        if not HAS_NATIVE_UIA:
            return None

        self._ensure_desktop_access()
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd or hwnd == 0:
            # Fallback: find the first non-minimized visible window from enumeration
            wins = self.enumerate_windows()
            return wins[0] if wins else None

        return self._build_window_info(hwnd, is_active=True)

    def enumerate_windows(self) -> List[WindowInfo]:
        """Enumerates visible, non-zero-sized desktop windows."""
        if not HAS_NATIVE_UIA:
            return []

        self._ensure_desktop_access()
        windows: List[WindowInfo] = []
        active_hwnd = self._user32.GetForegroundWindow()

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_cb(hwnd: int, lparam: int) -> bool:
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title:
                        rect = win32gui.GetWindowRect(hwnd)
                        # Filter out empty or invisible off-screen helper windows
                        if rect[2] > rect[0] and rect[3] > rect[1]:
                            w_info = self._build_window_info(hwnd, is_active=(hwnd == active_hwnd))
                            if w_info:
                                windows.append(w_info)
            except Exception:
                pass
            return True

        cb = WNDENUMPROC(enum_cb)
        h_desk = self._user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            self._user32.EnumDesktopWindows(h_desk, cb, 0)
        else:
            win32gui.EnumWindows(enum_cb, 0)

        return windows

    def _build_window_info(self, hwnd: int, is_active: bool = False) -> Optional[WindowInfo]:
        """Constructs WindowInfo for a window handle."""
        try:
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            is_minimized = (rect[0] <= -30000 or win32gui.IsIconic(hwnd) != 0)

            # Get process name safely
            proc_name = ""
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                # Avoid aggressive process handle queries; keep PID or class
                proc_name = f"PID:{pid}"
            except Exception:
                pass

            bounds = BoundingBox(
                left=max(0, rect[0]) if not is_minimized else 0,
                top=max(0, rect[1]) if not is_minimized else 0,
                right=max(0, rect[2]) if not is_minimized else 0,
                bottom=max(0, rect[3]) if not is_minimized else 0
            )

            return WindowInfo(
                hwnd=hwnd,
                title=title,
                process_name=proc_name,
                bounds=bounds,
                is_active=is_active,
                is_minimized=is_minimized,
                is_maximized=win32gui.IsZoomed(hwnd) != 0,
                class_name=class_name
            )
        except Exception as e:
            logger.debug(f"Error building WindowInfo for hwnd {hwnd}: {e}")
            return None

    def extract_elements(
        self,
        target_hwnd: Optional[int] = None,
        max_depth: int = 4,
        timeout_seconds: float = 3.0
    ) -> List[UIElement]:
        """
        Recursively extracts UI Automation tree controls up to max_depth.
        Protects against infinite recursion and respects the time budget.
        """
        if not HAS_NATIVE_UIA:
            logger.warning("Native UIA is not available in current environment.")
            return []

        self._ensure_desktop_access()
        start_time = time.perf_counter()

        target_control = None
        if target_hwnd:
            try:
                target_control = auto.ControlFromHandle(target_hwnd)
            except Exception as e:
                logger.warning(f"Could not get UIA control from hwnd {target_hwnd}: {e}")

        if not target_control:
            active_win = self.get_active_window()
            if active_win and active_win.hwnd:
                try:
                    target_control = auto.ControlFromHandle(active_win.hwnd)
                except Exception:
                    pass

        if not target_control:
            try:
                target_control = auto.GetRootControl()
            except Exception as e:
                logger.error(f"Failed to get root UIA control: {e}")
                return []

        elements: List[UIElement] = []
        visited = set()

        def _walk_tree(control: Any, parent_id: Optional[str], current_depth: int) -> None:
            if current_depth > max_depth:
                return
            if time.perf_counter() - start_time > timeout_seconds:
                logger.warning("UIA tree extraction hit timeout limit; returning partial elements.")
                return

            try:
                handle = getattr(control, "NativeWindowHandle", 0)
                auto_id = getattr(control, "AutomationId", "")
                name = getattr(control, "Name", "")
                ctrl_type = getattr(control, "ControlTypeName", "Unknown")

                key = (handle, auto_id, name, ctrl_type)
                if key in visited:
                    return
                visited.add(key)

                # Extract bounding rect
                rect = getattr(control, "BoundingRectangle", None)
                if rect and (rect.width() > 0 or rect.height() > 0):
                    bbox = BoundingBox(
                        left=rect.left,
                        top=rect.top,
                        right=rect.right,
                        bottom=rect.bottom,
                        width=rect.width(),
                        height=rect.height()
                    )
                else:
                    bbox = BoundingBox(0, 0, 0, 0)

                # Check if this control is a sensitive password input
                is_pwd = False
                try:
                    if getattr(control, "IsPasswordControl", False):
                        is_pwd = True
                    elif "password" in name.lower() or "password" in auto_id.lower():
                        is_pwd = True
                except Exception:
                    pass

                role = ctrl_type.replace("Control", "") if ctrl_type.endswith("Control") else ctrl_type

                ui_elem = UIElement(
                    parent_id=parent_id,
                    role=role,
                    control_type=ctrl_type,
                    name=name,
                    automation_id=auto_id,
                    class_name=getattr(control, "ClassName", ""),
                    bounding_box=bbox,
                    enabled=getattr(control, "IsEnabled", True),
                    visible=getattr(control, "IsOffscreen", False) is False,
                    focused=getattr(control, "HasKeyboardFocus", False),
                    source="UIA",
                    confidence=1.0,
                    is_sensitive=is_pwd
                )
                elements.append(ui_elem)

                # Recurse children
                for child in control.GetChildren():
                    _walk_tree(child, ui_elem.element_id, current_depth + 1)

            except Exception as e:
                logger.debug(f"Error inspecting UIA element at depth {current_depth}: {e}")

        _walk_tree(target_control, None, 0)
        logger.info(f"UIA extraction completed: found {len(elements)} elements in {time.perf_counter() - start_time:.3f}s")
        return elements


class MockUIAutomationProvider(UIAutomationProvider):
    """Deterministic mock provider for automated unit testing."""

    def __init__(
        self,
        mock_windows: Optional[List[WindowInfo]] = None,
        mock_elements: Optional[List[UIElement]] = None
    ) -> None:
        self.mock_windows = mock_windows or [
            WindowInfo(
                hwnd=1001,
                title="Example Dashboard",
                process_name="example.exe",
                bounds=BoundingBox(0, 0, 1920, 1080),
                is_active=True,
                is_minimized=False,
                is_maximized=True,
                class_name="ExampleMainWindow"
            )
        ]
        self.mock_elements = mock_elements or [
            UIElement(
                role="Window",
                control_type="WindowControl",
                name="Example Dashboard",
                bounding_box=BoundingBox(0, 0, 1920, 1080),
                source="UIA"
            ),
            UIElement(
                role="Button",
                control_type="ButtonControl",
                name="Download",
                automation_id="btn_download",
                bounding_box=BoundingBox(100, 150, 260, 200),
                enabled=True,
                visible=True,
                source="UIA"
            ),
            UIElement(
                role="Button",
                control_type="ButtonControl",
                name="Cancel",
                automation_id="btn_cancel",
                bounding_box=BoundingBox(280, 150, 420, 200),
                enabled=True,
                visible=True,
                source="UIA"
            ),
            UIElement(
                role="Edit",
                control_type="EditControl",
                name="Password",
                automation_id="input_password",
                bounding_box=BoundingBox(100, 220, 350, 260),
                is_sensitive=True,
                value="secret123",  # Automatically redacted by UIElement.__post_init__
                source="UIA"
            )
        ]

    def get_active_window(self) -> Optional[WindowInfo]:
        for w in self.mock_windows:
            if w.is_active:
                return w
        return self.mock_windows[0] if self.mock_windows else None

    def enumerate_windows(self) -> List[WindowInfo]:
        return list(self.mock_windows)

    def extract_elements(
        self,
        target_hwnd: Optional[int] = None,
        max_depth: int = 4,
        timeout_seconds: float = 3.0
    ) -> List[UIElement]:
        return list(self.mock_elements)
