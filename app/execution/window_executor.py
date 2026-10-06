"""
VisionPilot Window & Application Action Executor.

Implements safe, bounded window and application management:
- FOCUS_WINDOW / SWITCH_WINDOW: Safely activates window via user32 SetForegroundWindow
- LAUNCH_APPLICATION: Launches allowlisted desktop utilities (Notepad, Calculator, File Explorer)

STRICT SAFETY DEFENSES:
- Application Launch Allowlist: Only predefined safe system utilities are launchable.
- Arbitrary Executable Paths: User or model provided arbitrary .exe paths are rejected.
- Shell Avoidance: Uses subprocess.Popen with explicit arguments array, NEVER shell=True.
"""
import ctypes
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Set

from app.core.config import config
from app.core.exceptions import ExecutionError, SafetyViolationError
from app.core.logger import logger
from app.execution.schema import ActionRequest, ActionResult, ActionStatus


class WindowActionExecutor:
    """Executes safe window activation and allowlisted application launches."""

    # Explicit Allowlist of launchable application keys and their verified executable binaries
    ALLOWED_APPS: Dict[str, List[str]] = {
        "notepad": ["notepad.exe"],
        "calculator": ["calc.exe"],
        "explorer": ["explorer.exe"],
        "settings": ["cmd.exe", "/c", "start", "ms-settings:"],  # Windows Settings URI
    }

    def execute(self, request: ActionRequest) -> ActionResult:
        """Dispatches window or application action."""
        result = ActionResult(
            action_id=request.action_id,
            task_id=request.task_id,
            capability=request.capability,
            target_description=request.target.name or "window",
        )

        cap = request.capability
        try:
            if cap in ("SWITCH_WINDOW", "FOCUS_WINDOW"):
                return self._execute_focus_window(request, result)
            elif cap == "LAUNCH_APPLICATION":
                return self._execute_launch_app(request, result)
            else:
                result.mark_completed(ActionStatus.FAILED, f"Unsupported window capability '{cap}'.", error_code="UNSUPPORTED_CAPABILITY")
                return result
        except SafetyViolationError as e:
            logger.warning(f"Window safety violation for [{request.action_id}]: {e.message}")
            result.mark_completed(ActionStatus.BLOCKED, e.message, error_code="SECURITY_VIOLATION")
            return result
        except Exception as e:
            logger.error(f"Window action failed for [{request.action_id}]: {e}", exc_info=True)
            result.mark_completed(ActionStatus.FAILED, str(e), error_code="WINDOW_ACTION_FAILED")
            return result

    def _execute_focus_window(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        target_hwnd = req.parameters.get("hwnd")
        target_title = (req.parameters.get("window_title") or req.target.name or "").strip().lower()

        user32 = ctypes.windll.user32
        found_hwnd = 0

        # Direct HWND activation if valid
        if target_hwnd and user32.IsWindow(int(target_hwnd)):
            found_hwnd = int(target_hwnd)
        elif target_title:
            # Enumerate top-level windows to locate title match
            def enum_proc(hwnd: int, lparam: int) -> bool:
                nonlocal found_hwnd
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if target_title in buf.value.lower():
                            found_hwnd = hwnd
                            return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
            user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

        if not found_hwnd or not user32.IsWindow(found_hwnd):
            res.mark_completed(ActionStatus.FAILED, f"Could not find window matching '{target_title or target_hwnd}'.", error_code="WINDOW_NOT_FOUND")
            return res

        # Bring window to foreground safely
        user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(found_hwnd)
        evidence = {"hwnd": found_hwnd, "window_title": target_title}
        res.mark_completed(ActionStatus.SUCCESS, f"Focused window (HWND: {found_hwnd}).", evidence=evidence)
        return res

    def _execute_launch_app(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        app_name = (req.parameters.get("app_name") or req.target.name or "").strip().lower()
        if not app_name:
            res.mark_completed(ActionStatus.FAILED, "Missing 'app_name' parameter.", error_code="INVALID_PARAMETER")
            return res

        # Check Allowlist
        if app_name not in self.ALLOWED_APPS:
            allowed_list = list(self.ALLOWED_APPS.keys())
            raise SafetyViolationError(
                f"Application '{app_name}' is not in the allowlist. Allowed applications: {', '.join(allowed_list)}."
            )

        cmd_args = self.ALLOWED_APPS[app_name]
        try:
            # Spawn process without shell=True
            proc = subprocess.Popen(cmd_args, shell=False)
            evidence = {"app_name": app_name, "pid": proc.pid}
            res.mark_completed(ActionStatus.SUCCESS, f"Launched application '{app_name}' (PID: {proc.pid}).", evidence=evidence)
            return res
        except Exception as e:
            res.mark_completed(ActionStatus.FAILED, f"Failed to start application '{app_name}': {e}", error_code="PROCESS_SPAWN_FAILED")
            return res
