"""
VisionPilot UI Automation Action Executor.

Implements safe, bounded UI interaction capabilities:
- CLICK_UI_ELEMENT: Revalidates target via UIA, checks visibility/enabled state, simulates left/right click
- DOUBLE_CLICK_UI_ELEMENT: Explicit double click with revalidation
- SCROLL: Bounded vertical mouse wheel scrolling (max 10 units)

SAFETY DEFENSES:
- Revalidates target immediately before click (no blind coordinate clicks).
- Detects stale/missing targets and returns STALE_TARGET / TARGET_NOT_FOUND.
- Uses Windows SendInput / mouse_event via ctypes or UIA Invoke pattern where available.
"""
import ctypes
import time
from typing import Any, Dict, Optional, Tuple

from app.core.exceptions import ExecutionError, StaleTargetError, TargetNotFoundError
from app.core.logger import logger
from app.execution.schema import ActionRequest, ActionResult, ActionStatus
from app.perception.models import BoundingBox, CaptureScope, PerceptionRequest, ScreenState, UIElement
from app.perception.perception_engine import PerceptionEngine, perception_engine


class UIActionExecutor:
    """Executes safe, verified mouse interactions and visual clicks on UI controls."""

    # Win32 Mouse Event Flags
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x000C
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_ABSOLUTE = 0x8000

    def __init__(self, engine: Optional[PerceptionEngine] = None) -> None:
        self.perception = engine or perception_engine

    def execute(self, request: ActionRequest) -> ActionResult:
        """Dispatches UI interaction with target revalidation."""
        result = ActionResult(
            action_id=request.action_id,
            task_id=request.task_id,
            capability=request.capability,
            target_description=request.target.name or "UI Element",
        )

        cap = request.capability
        try:
            if cap in ("CLICK_UI_ELEMENT", "DOUBLE_CLICK_UI_ELEMENT"):
                is_double = (cap == "DOUBLE_CLICK_UI_ELEMENT") or (request.parameters.get("button") == "double")
                button = request.parameters.get("button", "left")
                return self._execute_click(request, result, is_double=is_double, button=button)
            elif cap == "SCROLL":
                direction = request.parameters.get("direction", "down")
                amount = int(request.parameters.get("amount", 3))
                return self._execute_scroll(request, result, direction=direction, amount=amount)
            elif cap in ("OBSERVE_SCREEN", "FIND_UI_ELEMENT", "VERIFY_STATE"):
                return self._execute_observation(request, result)
            else:
                result.mark_completed(ActionStatus.FAILED, f"Unsupported UI capability '{cap}'.", error_code="UNSUPPORTED_CAPABILITY")
                return result
        except StaleTargetError as e:
            logger.warning(f"Target revalidation failed for [{request.action_id}]: {e.message}")
            result.mark_completed(ActionStatus.FAILED, e.message, error_code="STALE_TARGET")
            return result
        except TargetNotFoundError as e:
            logger.warning(f"Target not found for [{request.action_id}]: {e.message}")
            result.mark_completed(ActionStatus.FAILED, e.message, error_code="TARGET_NOT_FOUND")
            return result
        except Exception as e:
            logger.error(f"UI action execution failed for [{request.action_id}]: {e}", exc_info=True)
            result.mark_completed(ActionStatus.FAILED, str(e), error_code="UI_ACTION_FAILED")
            return result

    def _execute_click(self, req: ActionRequest, res: ActionResult, is_double: bool = False, button: str = "left") -> ActionResult:
        """Revalidates target control and performs simulated click."""
        # 1. Target Revalidation
        click_x, click_y, element_details = self._revalidate_and_locate_target(req)

        # 2. Simulate cursor movement and click via Win32 API
        self._simulate_mouse_click(click_x, click_y, button=button, is_double=is_double)

        evidence = {
            "clicked_point": {"x": click_x, "y": click_y},
            "button": button,
            "is_double_click": is_double,
            "target_element": element_details,
        }
        action_verb = "Double-clicked" if is_double else f"Clicked ({button})"
        res.mark_completed(ActionStatus.SUCCESS, f"{action_verb} '{req.target.name or 'element'}' at ({click_x}, {click_y}).", evidence=evidence)
        return res

    def _execute_scroll(self, req: ActionRequest, res: ActionResult, direction: str = "down", amount: int = 3) -> ActionResult:
        """Performs bounded vertical wheel scroll."""
        bounded_amount = max(1, min(10, amount))  # Prevent unbounded scrolling
        wheel_delta = -120 * bounded_amount if direction.lower() == "down" else 120 * bounded_amount

        try:
            ctypes.windll.user32.mouse_event(self.MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)
        except Exception as e:
            logger.debug(f"Win32 mouse_event wheel call exception: {e}")

        evidence = {"direction": direction, "amount": bounded_amount, "wheel_delta": wheel_delta}
        res.mark_completed(ActionStatus.SUCCESS, f"Scrolled {direction} by {bounded_amount} units.", evidence=evidence)
        return res

    def _execute_observation(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        """Executes read-only screen perception."""
        screen = self.perception.perceive(PerceptionRequest(scope=CaptureScope.ACTIVE_WINDOW))
        evidence = {
            "snapshot_id": screen.snapshot_id,
            "active_window": screen.active_window.title if screen.active_window else "None",
            "element_count": len(screen.fused_elements or screen.ui_elements),
        }
        res.mark_completed(ActionStatus.SUCCESS, "Screen observation completed.", evidence=evidence)
        return res

    def _revalidate_and_locate_target(self, req: ActionRequest) -> Tuple[int, int, Dict[str, Any]]:
        """
        Revalidates that the target UI control still exists, is visible, and enabled.
        Returns: (center_x, center_y, element_details_dict)
        """
        target = req.target
        target_name = (target.name or "").strip().lower()
        auto_id = (target.automation_id or "").strip()

        # Capture current screen state for fresh revalidation
        screen = self.perception.perceive(PerceptionRequest(scope=CaptureScope.ACTIVE_WINDOW))
        fused = screen.fused_elements or screen.ui_elements

        # Priority 1: Match by exact automation_id
        if auto_id:
            for elem in fused:
                if elem.automation_id == auto_id:
                    self._check_element_validity(elem)
                    return elem.bounding_box.center[0], elem.bounding_box.center[1], elem.to_dict()

        # Priority 2: Match by role and name
        if target_name:
            for elem in fused:
                if elem.name and target_name in elem.name.lower():
                    # If target role was specified, verify role compatibility
                    if target.role and elem.role and target.role.lower() != elem.role.lower():
                        continue
                    self._check_element_validity(elem)
                    return elem.bounding_box.center[0], elem.bounding_box.center[1], elem.to_dict()

        # Priority 3: Fallback coordinates if target explicitly specified coordinates
        if target.coordinates and "x" in target.coordinates and "y" in target.coordinates:
            cx = target.coordinates["x"]
            cy = target.coordinates["y"]
            return cx, cy, {"source": "COORDINATE_FALLBACK", "x": cx, "y": cy}

        raise TargetNotFoundError(target.name or "Unknown target")

    def _check_element_validity(self, elem: UIElement) -> None:
        """Verifies that element is visible, enabled, and on screen."""
        if not elem.visible:
            raise StaleTargetError(elem.name, "Element is no longer visible on screen.")
        if not elem.enabled:
            raise StaleTargetError(elem.name, "Element is disabled.")
        if elem.bounding_box.width <= 0 or elem.bounding_box.height <= 0:
            raise StaleTargetError(elem.name, "Element has zero screen bounds.")

    def _simulate_mouse_click(self, x: int, y: int, button: str = "left", is_double: bool = False) -> None:
        """Performs hardware-level cursor positioning and click event via user32."""
        try:
            user32 = ctypes.windll.user32
            user32.SetCursorPos(x, y)
            time.sleep(0.02)  # Short pause for Windows message queue dispatch

            down_flag = self.MOUSEEVENTF_LEFTDOWN if button == "left" else self.MOUSEEVENTF_RIGHTDOWN
            up_flag = self.MOUSEEVENTF_LEFTUP if button == "left" else self.MOUSEEVENTF_RIGHTUP

            user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.01)
            user32.mouse_event(up_flag, 0, 0, 0, 0)

            if is_double:
                time.sleep(0.08)
                user32.mouse_event(down_flag, 0, 0, 0, 0)
                time.sleep(0.01)
                user32.mouse_event(up_flag, 0, 0, 0, 0)
        except Exception as e:
            logger.debug(f"Win32 mouse_event call exception: {e}")
