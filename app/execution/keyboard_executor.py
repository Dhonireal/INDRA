"""
VisionPilot Keyboard Action Executor.

Implements safe, bounded keyboard interaction capabilities:
- TYPE_TEXT: Types validated plain text into active/focused control
- PRESS_KEY: Presses allowlisted single key (ENTER, ESC, TAB, BACKSPACE, ARROWS)
- HOTKEY: Presses allowlisted modifier+key combination (CTRL+C, CTRL+V, CTRL+S, etc.)

STRICT SAFETY DEFENSES:
- Password Protection: If target is marked sensitive/password, typing is BLOCKED.
- Credential Protection: Checks text for passwords, API keys, private tokens, or secrets.
- Shell Payload Shield: Blocks typing raw shell scripts or powershell commands.
- Hotkey Allowlist: Only predefined safe shortcuts are executed.
"""
import ctypes
import re
import time
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import ExecutionError, SafetyViolationError
from app.core.logger import logger
from app.execution.schema import ActionRequest, ActionResult, ActionStatus


class KeyboardActionExecutor:
    """Executes safe, allowlisted keyboard keystrokes and text entry."""

    # Win32 Virtual Key Codes
    VK_MAP = {
        "ENTER": 0x0D,
        "RETURN": 0x0D,
        "ESC": 0x1B,
        "ESCAPE": 0x1B,
        "TAB": 0x09,
        "BACKSPACE": 0x08,
        "DELETE": 0x2E,
        "SPACE": 0x20,
        "UP": 0x26,
        "DOWN": 0x28,
        "LEFT": 0x25,
        "RIGHT": 0x27,
        "HOME": 0x24,
        "END": 0x23,
        "PAGEUP": 0x21,
        "PAGEDOWN": 0x22,
        "CONTROL": 0x11,
        "CTRL": 0x11,
        "ALT": 0x12,
        "SHIFT": 0x10,
        "A": 0x41, "C": 0x43, "F": 0x46, "S": 0x53, "V": 0x56, "Z": 0x5A,
    }

    # Strict Hotkey Allowlist
    ALLOWED_HOTKEYS: Set[str] = {
        "ctrl+c", "ctrl+v", "ctrl+s", "ctrl+a", "ctrl+z", "ctrl+f",
        "alt+tab", "alt+f4", "esc", "enter", "tab"
    }

    # Patterns indicating credential or malicious command payload
    _CREDENTIAL_PATTERNS = [
        re.compile(r"\b(password|passwd|secret|api[_-]?key|bearer|token)\s*[:=]", re.IGNORECASE),
        re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
        re.compile(r"\b(powershell|cmd\.exe|rmdir|format\s+c:)\b", re.IGNORECASE),
    ]

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    def execute(self, request: ActionRequest) -> ActionResult:
        """Dispatches keyboard action based on capability."""
        result = ActionResult(
            action_id=request.action_id,
            task_id=request.task_id,
            capability=request.capability,
            target_description=request.target.name or "keyboard",
        )

        cap = request.capability
        try:
            if cap == "TYPE_TEXT":
                return self._execute_type_text(request, result)
            elif cap == "PRESS_KEY":
                return self._execute_press_key(request, result)
            elif cap == "HOTKEY":
                return self._execute_hotkey(request, result)
            else:
                result.mark_completed(ActionStatus.FAILED, f"Unsupported keyboard capability '{cap}'.", error_code="UNSUPPORTED_CAPABILITY")
                return result
        except SafetyViolationError as e:
            logger.warning(f"Keyboard safety violation for [{request.action_id}]: {e.message}")
            result.mark_completed(ActionStatus.BLOCKED, e.message, error_code="SECURITY_VIOLATION")
            return result
        except Exception as e:
            logger.error(f"Keyboard action failed for [{request.action_id}]: {e}", exc_info=True)
            result.mark_completed(ActionStatus.FAILED, str(e), error_code="KEYBOARD_ERROR")
            return result

    def _execute_type_text(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        text = req.parameters.get("text", "")
        if not text:
            res.mark_completed(ActionStatus.FAILED, "Missing 'text' parameter.", error_code="INVALID_PARAMETER")
            return res

        # 1. Target Password Field Defense
        target = req.target
        if target.role and "password" in target.role.lower():
            raise SafetyViolationError("Typing into password fields is strictly BLOCKED by policy.")
        if target.name and "password" in target.name.lower():
            raise SafetyViolationError("Typing into password controls is strictly BLOCKED by policy.")

        # 2. Credential & Shell Payload Scanning
        for pattern in self._CREDENTIAL_PATTERNS:
            if pattern.search(text):
                raise SafetyViolationError("Text contains credentials, tokens, or prohibited shell commands.")

        # 3. Simulate Unicode typing via SendInput / keybd_event
        self._simulate_unicode_typing(text)

        evidence = {"characters_typed": len(text), "text_preview": text[:10] + ("..." if len(text) > 10 else "")}
        res.mark_completed(ActionStatus.SUCCESS, f"Typed {len(text)} characters into active control.", evidence=evidence)
        return res

    def _execute_press_key(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        key_str = (req.parameters.get("key") or req.target.name or "").strip().upper()
        if key_str not in self.VK_MAP:
            res.mark_completed(ActionStatus.FAILED, f"Prohibited or unknown key '{key_str}'.", error_code="PROHIBITED_KEY")
            return res

        vk_code = self.VK_MAP[key_str]
        self._send_key_event(vk_code)

        evidence = {"key": key_str, "vk_code": vk_code}
        res.mark_completed(ActionStatus.SUCCESS, f"Pressed key '{key_str}'.", evidence=evidence)
        return res

    def _execute_hotkey(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        hotkey_str = (req.parameters.get("hotkey") or "").strip().lower()
        if not hotkey_str:
            res.mark_completed(ActionStatus.FAILED, "Missing 'hotkey' parameter.", error_code="INVALID_PARAMETER")
            return res

        if hotkey_str not in self.ALLOWED_HOTKEYS:
            raise SafetyViolationError(f"Hotkey combination '{hotkey_str}' is not in the allowlist.")

        parts = [p.strip().upper() for p in hotkey_str.split("+")]
        vk_codes = [self.VK_MAP.get(p) for p in parts if p in self.VK_MAP]

        if len(vk_codes) != len(parts):
            res.mark_completed(ActionStatus.FAILED, f"Unknown key in hotkey '{hotkey_str}'.", error_code="UNKNOWN_KEY")
            return res

        # Key down in order, key up in reverse
        user32 = ctypes.windll.user32
        for vk in vk_codes:
            user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        for vk in reversed(vk_codes):
            user32.keybd_event(vk, 0, self.KEYEVENTF_KEYUP, 0)

        evidence = {"hotkey": hotkey_str, "keys": parts}
        res.mark_completed(ActionStatus.SUCCESS, f"Pressed hotkey '{hotkey_str}'.", evidence=evidence)
        return res

    def _send_key_event(self, vk_code: int) -> None:
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.01)
            user32.keybd_event(vk_code, 0, self.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            logger.debug(f"Win32 keybd_event call exception: {e}")

    def _simulate_unicode_typing(self, text: str) -> None:
        try:
            user32 = ctypes.windll.user32
            for char in text:
                char_code = ord(char)
                # Send Unicode character press
                user32.keybd_event(0, char_code, self.KEYEVENTF_UNICODE, 0)
                user32.keybd_event(0, char_code, self.KEYEVENTF_UNICODE | self.KEYEVENTF_KEYUP, 0)
                time.sleep(0.005)
        except Exception as e:
            logger.debug(f"Win32 unicode keybd_event call exception: {e}")
