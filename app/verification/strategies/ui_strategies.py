"""
VisionPilot UI Verification Strategies.

Implements deterministic postcondition verification for UI and Window actions:
- UIElementPresentVerifier (verifies control presence and visibility)
- UIElementAbsentVerifier (verifies control disappearance / modal close)
- TextPresentVerifier (verifies text appearance via OCR or UIA)
- TextAbsentVerifier (verifies text disappearance)
- WindowActiveVerifier (verifies window focus and active state)
- ValueChangedVerifier (verifies control text or value modification)

CRITICAL SAFETY & PRIVACY:
- Leverages Phase 5 PerceptionEngine and ScreenState (UIA + native OCR).
- Ephemeral in-memory inspection (zero disk screenshot writes).
- Treats all screen and OCR text as UNTRUSTED observational evidence.
- Deterministic comparison: never delegates simple verification to an LLM.
"""
from typing import Any, Dict, List, Optional
import time

from app.core.logger import logger
from app.execution.schema import ActionResult
from app.perception.models import ScreenState, UIElement, OCRTextRegion, WindowInfo
from app.perception.perception_engine import PerceptionEngine
from app.verification.schema import (
    ExpectedResult, ExpectedResultType, VerificationConfidence,
    VerificationResult, VerificationStatus
)
from app.verification.strategies.base import VerificationStrategy


class UIElementPresentVerifier(VerificationStrategy):
    """Verifies that an expected UI element is present and visible on screen."""

    def __init__(self, perception_engine: Optional[PerceptionEngine] = None) -> None:
        self.perception_engine = perception_engine

    @property
    def strategy_name(self) -> str:
        return "UIElementPresentVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type in (ExpectedResultType.ELEMENT_PRESENT, ExpectedResultType.UI_STATE)

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"target": expected.target, "must_be_visible": True}
        )

        screen_state = self._get_screen_state(context)
        if not screen_state:
            res.mark_uncertain(self.strategy_name, "Perception state unavailable for UI verification.")
            return res

        target_query = expected.target.lower().strip()
        matched_element: Optional[UIElement] = None

        # 1. Look in UIA fused elements by automation_id, name, or role
        for el in screen_state.fused_elements:
            if not el.visible:
                continue
            if el.automation_id and el.automation_id.lower() == target_query:
                matched_element = el
                break
            if target_query in el.name.lower():
                matched_element = el
                break
            if el.control_type.lower() == target_query:
                matched_element = el
                break

        # 2. Check OCR regions if not found in UIA
        if not matched_element:
            for ocr in screen_state.ocr_regions:
                if target_query in ocr.text.lower():
                    evidence = {
                        "source": "OCR",
                        "text": ocr.text,
                        "bounds": ocr.bounding_box.to_dict(),
                        "confidence": ocr.confidence,
                    }
                    res.actual_state = evidence
                    res.mark_verified(self.strategy_name, VerificationConfidence.MEDIUM, evidence=evidence)
                    return res

        if matched_element:
            evidence = {
                "source": "UIA",
                "name": matched_element.name,
                "role": matched_element.role,
                "automation_id": matched_element.automation_id,
                "visible": matched_element.visible,
                "enabled": matched_element.enabled,
                "bounds": matched_element.bounding_box.to_dict(),
            }
            res.actual_state = evidence
            res.mark_verified(self.strategy_name, VerificationConfidence.STRONG, evidence=evidence)
        else:
            res.actual_state = {"present": False, "target": expected.target}
            res.mark_failed(
                self.strategy_name,
                f"Expected UI element '{expected.target}' was not found on screen.",
                evidence={"elements_checked": len(screen_state.fused_elements)}
            )

        return res

    def _get_screen_state(self, context: Optional[Dict[str, Any]]) -> Optional[ScreenState]:
        if context and "screen_state" in context and isinstance(context["screen_state"], ScreenState):
            return context["screen_state"]
        if self.perception_engine:
            try:
                return self.perception_engine.perceive()
            except Exception as e:
                logger.warning(f"UIElementPresentVerifier perception failed: {e}")
        return None


class UIElementAbsentVerifier(VerificationStrategy):
    """Verifies that a specified UI element is no longer present or visible (e.g. modal closed)."""

    def __init__(self, perception_engine: Optional[PerceptionEngine] = None) -> None:
        self.perception_engine = perception_engine

    @property
    def strategy_name(self) -> str:
        return "UIElementAbsentVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.ELEMENT_ABSENT

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"target": expected.target, "should_be_absent": True}
        )

        screen_state = self._get_screen_state(context)
        if not screen_state:
            res.mark_uncertain(self.strategy_name, "Perception state unavailable for UI verification.")
            return res

        target_query = expected.target.lower().strip()
        still_present = False
        matching_info: Dict[str, Any] = {}

        for el in screen_state.fused_elements:
            if not el.visible:
                continue
            if (el.automation_id and el.automation_id.lower() == target_query) or (target_query in el.name.lower()):
                still_present = True
                matching_info = {"name": el.name, "automation_id": el.automation_id, "visible": el.visible}
                break

        res.actual_state = {"present": still_present, "element": matching_info}

        if still_present:
            res.mark_failed(
                self.strategy_name,
                f"Element '{expected.target}' is still visible on screen.",
                evidence=matching_info
            )
        else:
            res.mark_verified(
                self.strategy_name,
                VerificationConfidence.STRONG,
                evidence={"element_absent": True, "target": expected.target}
            )

        return res

    def _get_screen_state(self, context: Optional[Dict[str, Any]]) -> Optional[ScreenState]:
        if context and "screen_state" in context and isinstance(context["screen_state"], ScreenState):
            return context["screen_state"]
        if self.perception_engine:
            try:
                return self.perception_engine.perceive()
            except Exception as e:
                logger.warning(f"UIElementAbsentVerifier perception failed: {e}")
        return None


class TextPresentVerifier(VerificationStrategy):
    """Verifies that an expected text snippet is present on screen via OCR or UIA."""

    def __init__(self, perception_engine: Optional[PerceptionEngine] = None) -> None:
        self.perception_engine = perception_engine

    @property
    def strategy_name(self) -> str:
        return "TextPresentVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.TEXT_PRESENT

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"text": expected.target}
        )

        screen_state = self._get_screen_state(context)
        if not screen_state:
            res.mark_uncertain(self.strategy_name, "Perception state unavailable for OCR verification.")
            return res

        expected_snippet = (expected.expected_value or expected.target or "").lower().strip()
        if not expected_snippet:
            res.mark_failed(self.strategy_name, "Empty expected text query.")
            return res

        # 1. Search UIA element text
        for el in screen_state.fused_elements:
            if not el.visible:
                continue
            if expected_snippet in el.name.lower() or expected_snippet in el.text.lower():
                evidence = {"source": "UIA", "matched_text": el.name or el.text, "role": el.role}
                res.actual_state = evidence
                res.mark_verified(self.strategy_name, VerificationConfidence.STRONG, evidence=evidence)
                return res

        # 2. Search OCR text regions
        for ocr in screen_state.ocr_regions:
            if expected_snippet in ocr.text.lower():
                evidence = {
                    "source": "OCR",
                    "matched_text": ocr.text,
                    "confidence": ocr.confidence,
                    "bounds": ocr.bounding_box.to_dict()
                }
                res.actual_state = evidence
                res.mark_verified(self.strategy_name, VerificationConfidence.MEDIUM, evidence=evidence)
                return res

        res.actual_state = {"text_found": False, "query": expected_snippet}
        res.mark_failed(
            self.strategy_name,
            f"Expected text '{expected_snippet}' was not observed on screen.",
            evidence={"ocr_regions_checked": len(screen_state.ocr_regions)}
        )
        return res

    def _get_screen_state(self, context: Optional[Dict[str, Any]]) -> Optional[ScreenState]:
        if context and "screen_state" in context and isinstance(context["screen_state"], ScreenState):
            return context["screen_state"]
        if self.perception_engine:
            try:
                return self.perception_engine.perceive()
            except Exception as e:
                logger.warning(f"TextPresentVerifier perception failed: {e}")
        return None


class TextAbsentVerifier(VerificationStrategy):
    """Verifies that an expected text snippet is NOT present on screen."""

    def __init__(self, perception_engine: Optional[PerceptionEngine] = None) -> None:
        self.perception_engine = perception_engine

    @property
    def strategy_name(self) -> str:
        return "TextAbsentVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.TEXT_ABSENT

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"text": expected.target, "should_be_absent": True}
        )

        screen_state = self._get_screen_state(context)
        if not screen_state:
            res.mark_uncertain(self.strategy_name, "Perception state unavailable for text verification.")
            return res

        expected_snippet = (expected.expected_value or expected.target or "").lower().strip()
        found = False
        matching_text = ""

        for ocr in screen_state.ocr_regions:
            if expected_snippet in ocr.text.lower():
                found = True
                matching_text = ocr.text
                break

        res.actual_state = {"found": found, "matching_text": matching_text}

        if found:
            res.mark_failed(
                self.strategy_name,
                f"Text '{expected_snippet}' is still visible on screen.",
                evidence={"found_text": matching_text}
            )
        else:
            res.mark_verified(
                self.strategy_name,
                VerificationConfidence.MEDIUM,
                evidence={"text_absent": True, "query": expected_snippet}
            )

        return res

    def _get_screen_state(self, context: Optional[Dict[str, Any]]) -> Optional[ScreenState]:
        if context and "screen_state" in context and isinstance(context["screen_state"], ScreenState):
            return context["screen_state"]
        if self.perception_engine:
            try:
                return self.perception_engine.perceive()
            except Exception as e:
                logger.warning(f"TextAbsentVerifier perception failed: {e}")
        return None


class WindowActiveVerifier(VerificationStrategy):
    """Verifies that an expected window exists and is in the active foreground."""

    def __init__(self, perception_engine: Optional[PerceptionEngine] = None) -> None:
        self.perception_engine = perception_engine

    @property
    def strategy_name(self) -> str:
        return "WindowActiveVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.WINDOW_ACTIVE

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"window_target": expected.target, "must_be_active": True}
        )

        screen_state = self._get_screen_state(context)
        if not screen_state:
            res.mark_uncertain(self.strategy_name, "Perception state unavailable for window verification.")
            return res

        target = expected.target.lower().strip()
        active_win = screen_state.active_window

        # Check active window first
        if active_win and (target in active_win.title.lower() or target in active_win.process_name.lower()):
            evidence = {
                "hwnd": active_win.hwnd,
                "title": active_win.title,
                "process_name": active_win.process_name,
                "is_active": True,
            }
            res.actual_state = evidence
            res.mark_verified(self.strategy_name, VerificationConfidence.STRONG, evidence=evidence)
            return res

        # Check other windows if not active foreground
        matching_window: Optional[WindowInfo] = None
        for w in screen_state.windows:
            if target in w.title.lower() or target in w.process_name.lower():
                matching_window = w
                break

        if matching_window:
            evidence = {
                "hwnd": matching_window.hwnd,
                "title": matching_window.title,
                "process_name": matching_window.process_name,
                "is_active": False,
            }
            res.actual_state = evidence
            res.mark_failed(
                self.strategy_name,
                f"Window '{matching_window.title}' exists but is not in foreground.",
                evidence=evidence
            )
        else:
            res.actual_state = {"active_window": active_win.title if active_win else None, "found": False}
            res.mark_failed(
                self.strategy_name,
                f"Expected window '{expected.target}' was not found in desktop windows.",
                evidence={"total_windows": len(screen_state.windows)}
            )

        return res

    def _get_screen_state(self, context: Optional[Dict[str, Any]]) -> Optional[ScreenState]:
        if context and "screen_state" in context and isinstance(context["screen_state"], ScreenState):
            return context["screen_state"]
        if self.perception_engine:
            try:
                return self.perception_engine.perceive()
            except Exception as e:
                logger.warning(f"WindowActiveVerifier perception failed: {e}")
        return None


class ValueChangedVerifier(VerificationStrategy):
    """Verifies that a control's value or text changed after an action (e.g. TYPE_TEXT)."""

    @property
    def strategy_name(self) -> str:
        return "ValueChangedVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type in (ExpectedResultType.VALUE_CHANGED, ExpectedResultType.VALUE_EQUALS)

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"expected_value": expected.expected_value}
        )

        # Context or action result evidence
        current_value = ""
        if context and "control_value" in context:
            current_value = context["control_value"]
        elif action_result.evidence and "typed_text" in action_result.evidence:
            current_value = action_result.evidence["typed_text"]
        elif action_result.evidence and "value" in action_result.evidence:
            current_value = action_result.evidence["value"]

        expected_val = str(expected.expected_value or "")

        res.actual_state = {"current_value": current_value, "before_value": before_state}

        if expected.type == ExpectedResultType.VALUE_EQUALS:
            if current_value == expected_val:
                res.mark_verified(
                    self.strategy_name,
                    VerificationConfidence.STRONG,
                    evidence={"value": current_value, "expected": expected_val}
                )
            else:
                res.mark_failed(
                    self.strategy_name,
                    f"Value '{current_value}' does not match expected '{expected_val}'.",
                    evidence={"actual": current_value, "expected": expected_val}
                )
        else:  # VALUE_CHANGED
            if before_state is not None and current_value == before_state:
                res.mark_failed(
                    self.strategy_name,
                    f"Value did not change from initial state ('{current_value}').",
                    evidence={"value": current_value}
                )
            else:
                res.mark_verified(
                    self.strategy_name,
                    VerificationConfidence.STRONG,
                    evidence={"value": current_value}
                )

        return res


class StructuredStateVerifier(VerificationStrategy):
    """Verifies exploratory or read-only structured operations (FIND_FILE, OBSERVE_SCREEN, FIND_UI_ELEMENT, SCROLL)."""

    @property
    def strategy_name(self) -> str:
        return "StructuredStateVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.CUSTOM_STRUCTURED_STATE

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"capability": action_result.capability}
        )
        if action_result.success:
            res.mark_verified(
                self.strategy_name,
                VerificationConfidence.STRONG,
                evidence=action_result.evidence or {"success": True}
            )
        else:
            res.mark_failed(
                self.strategy_name,
                f"Action '{action_result.capability}' failed: {action_result.message}",
                evidence=action_result.evidence
            )
        return res

