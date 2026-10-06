"""
VisionPilot Screen Perception Data Models.

Defines strongly typed, framework-agnostic models for bounding boxes,
UI elements, OCR text regions, window telemetry, perception requests,
and structured ScreenState snapshots.

READ-ONLY: Perception models strictly convey observed desktop state
without containing execution, automation, or input simulation logic.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any
import uuid


class CaptureScope(str, Enum):
    """Scope boundaries for desktop perception capture."""
    ACTIVE_WINDOW = "ACTIVE_WINDOW"
    PRIMARY_SCREEN = "PRIMARY_SCREEN"
    ALL_SCREENS = "ALL_SCREENS"
    SPECIFIC_WINDOW = "SPECIFIC_WINDOW"


@dataclass(frozen=True)
class BoundingBox:
    """Explicit screen coordinate rectangle in desktop pixels."""
    left: int
    top: int
    right: int
    bottom: int
    width: int = 0
    height: int = 0

    def __post_init__(self) -> None:
        computed_w = max(0, self.right - self.left)
        computed_h = max(0, self.bottom - self.top)
        # Handle cases where width/height were passed or need computing
        if self.width <= 0:
            object.__setattr__(self, "width", computed_w)
        if self.height <= 0:
            object.__setattr__(self, "height", computed_h)

    @classmethod
    def from_xywh(cls, x: int, y: int, width: int, height: int) -> "BoundingBox":
        return cls(
            left=x,
            top=y,
            right=x + width,
            bottom=y + height,
            width=width,
            height=height
        )

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + self.width // 2, self.top + self.height // 2)

    @property
    def area(self) -> int:
        return self.width * self.height

    def contains_point(self, x: int, y: int) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def intersects(self, other: "BoundingBox") -> bool:
        return not (
            self.right <= other.left or
            self.left >= other.right or
            self.bottom <= other.top or
            self.top >= other.bottom
        )

    def intersection(self, other: "BoundingBox") -> Optional["BoundingBox"]:
        if not self.intersects(other):
            return None
        inter_left = max(self.left, other.left)
        inter_top = max(self.top, other.top)
        inter_right = min(self.right, other.right)
        inter_bottom = min(self.bottom, other.bottom)
        return BoundingBox(
            left=inter_left,
            top=inter_top,
            right=inter_right,
            bottom=inter_bottom
        )

    def iou(self, other: "BoundingBox") -> float:
        """Computes Intersection over Union (IoU) metric for deduplication."""
        inter = self.intersection(other)
        if not inter or inter.area <= 0:
            return 0.0
        union_area = self.area + other.area - inter.area
        if union_area <= 0:
            return 0.0
        return inter.area / union_area

    def to_dict(self) -> Dict[str, int]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "width": self.width,
            "height": self.height
        }


@dataclass
class UIElement:
    """Strongly typed representation of an observed UI accessibility control."""
    element_id: str = field(default_factory=lambda: f"elem_{uuid.uuid4().hex[:10]}")
    parent_id: Optional[str] = None
    role: str = "Unknown"                   # e.g., "Button", "Edit", "MenuItem", "Pane"
    control_type: str = "Unknown"           # e.g., "ButtonControl", "EditControl"
    name: str = ""                          # Accessible display name
    automation_id: str = ""                 # Developer AutomationId if set
    class_name: str = ""                    # Win32/WPF/UWP window/control class
    bounding_box: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 0, 0))
    enabled: bool = True
    visible: bool = True
    focused: bool = False
    selected: bool = False
    checked: Optional[bool] = None
    expanded: Optional[bool] = None
    value: Optional[str] = None
    text: Optional[str] = None
    source: str = "UIA"                     # "UIA", "OCR", or "UIA+OCR"
    confidence: float = 1.0
    is_sensitive: bool = False              # Marked True for password/credential inputs
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Enforce Rule 5 & Privacy: Never retain plain text values for sensitive password fields
        if self.is_sensitive:
            self.value = "[REDACTED]"
            self.text = "[REDACTED]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_id": self.element_id,
            "parent_id": self.parent_id,
            "role": self.role,
            "control_type": self.control_type,
            "name": self.name,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "bounding_box": self.bounding_box.to_dict(),
            "enabled": self.enabled,
            "visible": self.visible,
            "focused": self.focused,
            "selected": self.selected,
            "checked": self.checked,
            "expanded": self.expanded,
            "value": "[REDACTED]" if self.is_sensitive else self.value,
            "text": "[REDACTED]" if self.is_sensitive else self.text,
            "source": self.source,
            "confidence": self.confidence,
            "is_sensitive": self.is_sensitive
        }


@dataclass
class OCRTextRegion:
    """Recognized optical text region extracted from on-demand screen capture."""
    text: str
    bounding_box: BoundingBox
    confidence: float = 1.0
    language: str = "en-US"
    source: str = "OCR"
    trust_level: str = "UNTRUSTED"          # Prompt-injection preparation: all screen text is untrusted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "language": self.language,
            "source": self.source,
            "trust_level": self.trust_level
        }


@dataclass
class WindowInfo:
    """Observed top-level desktop window telemetry."""
    hwnd: int
    title: str
    process_name: str = ""
    bounds: BoundingBox = field(default_factory=lambda: BoundingBox(0, 0, 0, 0))
    is_active: bool = False
    is_minimized: bool = False
    is_maximized: bool = False
    class_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hwnd": self.hwnd,
            "title": self.title,
            "process_name": self.process_name,
            "bounds": self.bounds.to_dict(),
            "is_active": self.is_active,
            "is_minimized": self.is_minimized,
            "is_maximized": self.is_maximized,
            "class_name": self.class_name
        }


@dataclass
class PerceptionRequest:
    """Strongly typed parameters for an on-demand perception scan."""
    scope: CaptureScope = CaptureScope.ACTIVE_WINDOW
    include_ui_elements: bool = True
    include_ocr: bool = True
    include_screenshot: bool = False        # Default False for privacy
    target_window_hwnd: Optional[int] = None
    timeout_seconds: float = 5.0
    privacy_mode: bool = True


@dataclass
class GroundingCandidate:
    """Scored candidate UI element resulting from natural language visual grounding."""
    element: UIElement
    score: float                            # 0.0 to 1.0 match score
    match_strategy: str                     # "exact_name", "fuzzy_name", "automation_id", "ocr_text", "role_match"
    confidence_tier: str                    # "HIGH", "MEDIUM", "LOW"
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element": self.element.to_dict(),
            "score": self.score,
            "match_strategy": self.match_strategy,
            "confidence_tier": self.confidence_tier,
            "rationale": self.rationale
        }


@dataclass
class ScreenState:
    """Immutable, machine-readable snapshot of desktop perception state."""
    snapshot_id: str = field(default_factory=lambda: f"snap_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_window: Optional[WindowInfo] = None
    windows: List[WindowInfo] = field(default_factory=list)
    ui_elements: List[UIElement] = field(default_factory=list)
    ocr_regions: List[OCRTextRegion] = field(default_factory=list)
    fused_elements: List[UIElement] = field(default_factory=list)
    screen_dimensions: Tuple[int, int] = (1920, 1080)
    display_count: int = 1
    dpi_scale: float = 1.0
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    screenshot_bytes: Optional[bytes] = None  # None by default (ephemeral memory)

    def find_elements_by_role(self, role: str) -> List[UIElement]:
        """Find elements matching a specific role (e.g. 'Button', 'Edit')."""
        target = role.lower()
        return [
            e for e in self.fused_elements
            if e.role.lower() == target or e.control_type.lower().startswith(target)
        ]

    def find_elements_by_name(self, name_substr: str, case_sensitive: bool = False) -> List[UIElement]:
        """Find elements whose name contains substring."""
        if not case_sensitive:
            target = name_substr.lower()
            return [e for e in self.fused_elements if target in e.name.lower()]
        return [e for e in self.fused_elements if name_substr in e.name]

    def find_elements_in_region(self, region: BoundingBox) -> List[UIElement]:
        """Find elements intersecting or contained within a bounding box."""
        return [e for e in self.fused_elements if region.intersects(e.bounding_box)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "windows": [w.to_dict() for w in self.windows],
            "ui_elements_count": len(self.ui_elements),
            "ocr_regions_count": len(self.ocr_regions),
            "fused_elements_count": len(self.fused_elements),
            "fused_elements": [e.to_dict() for e in self.fused_elements],
            "screen_dimensions": list(self.screen_dimensions),
            "display_count": self.display_count,
            "dpi_scale": self.dpi_scale,
            "sources": self.sources,
            "metadata": self.metadata
        }
