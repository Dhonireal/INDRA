"""
VisionPilot Visual Grounding and UIA + OCR Fusion Subsystem.

Combines accessibility tree controls with optical character recognition regions
into a unified, deduplicated perceptual representation.
Provides deterministic natural-language element grounding without LLM hallucination.

READ-ONLY: Grounding identifies candidate elements and their screen coordinates;
it never triggers clicks or interacts with the system.
"""
from typing import List, Optional, Tuple, Dict, Any
import re

from app.core.logger import logger
from app.perception.models import (
    UIElement, OCRTextRegion, BoundingBox, GroundingCandidate, ScreenState
)


class PerceptionFuser:
    """Fuses UI Automation elements with OCR text regions using spatial & semantic alignment."""

    def __init__(self, iou_threshold: float = 0.3) -> None:
        self.iou_threshold = iou_threshold

    def fuse(
        self,
        uia_elements: List[UIElement],
        ocr_regions: List[OCRTextRegion]
    ) -> List[UIElement]:
        """
        Merges UIA controls and OCR text regions into a single deduplicated element list.
        """
        fused: List[UIElement] = []
        matched_ocr_indices = set()

        for uia in uia_elements:
            matched_ocr = None
            best_iou = 0.0

            # Find best overlapping or enclosing OCR region
            for idx, ocr in enumerate(ocr_regions):
                if idx in matched_ocr_indices:
                    continue

                iou = uia.bounding_box.iou(ocr.bounding_box)
                # Check either IoU overlap or containment
                is_contained = uia.bounding_box.intersects(ocr.bounding_box)

                if (iou >= self.iou_threshold or is_contained):
                    # Also check text/name similarity
                    norm_uia = self._normalize_text(uia.name)
                    norm_ocr = self._normalize_text(ocr.text)
                    if norm_uia and norm_ocr and (norm_uia in norm_ocr or norm_ocr in norm_uia):
                        matched_ocr = ocr
                        matched_ocr_indices.add(idx)
                        break
                    elif iou > best_iou:
                        best_iou = iou
                        matched_ocr = ocr

            if matched_ocr and (best_iou >= self.iou_threshold or uia.name):
                # Fuse element
                fused_elem = UIElement(
                    element_id=uia.element_id,
                    parent_id=uia.parent_id,
                    role=uia.role,
                    control_type=uia.control_type,
                    name=uia.name or matched_ocr.text,
                    automation_id=uia.automation_id,
                    class_name=uia.class_name,
                    bounding_box=uia.bounding_box if uia.bounding_box.area > 0 else matched_ocr.bounding_box,
                    enabled=uia.enabled,
                    visible=uia.visible,
                    focused=uia.focused,
                    selected=uia.selected,
                    checked=uia.checked,
                    expanded=uia.expanded,
                    value=uia.value,
                    text=matched_ocr.text if not uia.is_sensitive else "[REDACTED]",
                    source="UIA+OCR",
                    confidence=min(1.0, (uia.confidence + matched_ocr.confidence) / 2.0 + 0.1),
                    is_sensitive=uia.is_sensitive,
                    metadata={
                        **uia.metadata,
                        "fused_ocr_text": matched_ocr.text,
                        "ocr_confidence": matched_ocr.confidence
                    }
                )
                fused.append(fused_elem)
            else:
                fused.append(uia)

        # Include remaining un-fused OCR regions as text elements
        for idx, ocr in enumerate(ocr_regions):
            if idx not in matched_ocr_indices:
                text_elem = UIElement(
                    role="Text",
                    control_type="TextControl",
                    name=ocr.text,
                    bounding_box=ocr.bounding_box,
                    enabled=True,
                    visible=True,
                    text=ocr.text,
                    source="OCR",
                    confidence=ocr.confidence,
                    is_sensitive=False,
                    metadata={"trust_level": ocr.trust_level}
                )
                fused.append(text_elem)

        logger.debug(
            f"Perception fusion completed: {len(uia_elements)} UIA + "
            f"{len(ocr_regions)} OCR -> {len(fused)} fused elements"
        )
        return fused

    @staticmethod
    def _normalize_text(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip().lower()


class VisualGrounder:
    """Matches natural language descriptions to concrete on-screen candidate elements."""

    def __init__(self, fuser: Optional[PerceptionFuser] = None) -> None:
        self.fuser = fuser or PerceptionFuser()

    def ground(
        self,
        query: str,
        screen_state: ScreenState,
        preferred_role: Optional[str] = None
    ) -> List[GroundingCandidate]:
        """
        Locates UI elements corresponding to the visual query.
        Returns a sorted list of GroundingCandidates from highest to lowest score.
        """
        if not query or not query.strip():
            return []

        norm_query = query.strip().lower()
        candidates: List[GroundingCandidate] = []

        elements = screen_state.fused_elements or screen_state.ui_elements

        for elem in elements:
            score, strategy, tier, rationale = self._score_element(elem, norm_query, preferred_role)
            if score > 0.2:
                candidates.append(GroundingCandidate(
                    element=elem,
                    score=score,
                    match_strategy=strategy,
                    confidence_tier=tier,
                    rationale=rationale
                ))

        # Sort descending by score
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _score_element(
        self,
        elem: UIElement,
        norm_query: str,
        preferred_role: Optional[str]
    ) -> Tuple[float, str, str, str]:
        """Calculates deterministic matching score between query and UI element."""
        name = (elem.name or "").strip().lower()
        auto_id = (elem.automation_id or "").strip().lower()
        role = (elem.role or "").strip().lower()

        # 1. Exact Name + Role Match
        if preferred_role and role == preferred_role.lower() and name == norm_query:
            return 1.0, "exact_name_and_role", "HIGH", f"Exact name '{elem.name}' and matching role '{elem.role}'"

        # 2. Exact Name Match
        if name == norm_query:
            return 0.95, "exact_name", "HIGH", f"Exact name match on '{elem.name}'"

        # 3. Exact AutomationId Match
        if auto_id and (auto_id == norm_query or norm_query in auto_id):
            return 0.90, "automation_id", "HIGH", f"AutomationId match '{elem.automation_id}'"

        # 4. Substring Name Match
        if norm_query in name or (name and name in norm_query):
            score = 0.80 if len(name) > 3 else 0.65
            return score, "substring_name", "MEDIUM", f"Substring match in name '{elem.name}'"

        # 5. OCR Text Match
        if elem.text:
            text = elem.text.strip().lower()
            if norm_query in text or text in norm_query:
                return 0.75, "ocr_text", "MEDIUM", f"OCR recognized text match '{elem.text}'"

        # 6. Preferred Role Match alone
        if preferred_role and role == preferred_role.lower():
            return 0.40, "role_only", "LOW", f"Role match '{elem.role}' without name alignment"

        return 0.0, "none", "NONE", ""
