"""
VisionPilot Task and Command Schemas.

Defines strongly typed domain models for command requests, command context,
lifecycle states, and structured task requests for the future AI Task Planner.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import platform
from typing import Any, Dict, Optional
import uuid


class CommandSource(str, Enum):
    TEXT = "TEXT"
    VOICE = "VOICE"
    API = "API"
    SYSTEM = "SYSTEM"


class CommandStatus(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    NORMALIZING = "NORMALIZING"
    QUEUED = "QUEUED"
    READY_FOR_PLANNING = "READY_FOR_PLANNING"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass
class CommandContext:
    """Lightweight, non-intrusive runtime metadata for planning."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    os_platform: str = field(default_factory=platform.platform)
    machine: str = field(default_factory=platform.machine)
    app_version: str = "0.1.0"
    active_runtime: str = "Windows Win32 Native"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandRequest:
    """Strongly typed model representing a user's raw and processed command."""
    raw_text: str
    command_id: str = field(default_factory=lambda: f"cmd_{uuid.uuid4().hex[:12]}")
    normalized_text: str = ""
    source: CommandSource = CommandSource.TEXT
    status: CommandStatus = CommandStatus.RECEIVED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context: CommandContext = field(default_factory=CommandContext)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_cancelled: bool = False

    def mark_status(self, new_status: CommandStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)
        if new_status == CommandStatus.CANCELLED:
            self.is_cancelled = True


@dataclass
class TaskRequest:
    """Stable structured task payload contract for the future AI Task Planner (Phase 6)."""
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    command_id: str = ""
    prompt: str = ""
    source: CommandSource = CommandSource.TEXT
    context: CommandContext = field(default_factory=CommandContext)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "READY_FOR_PLANNING"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """Structured result of command validation, normalization, and task creation."""
    success: bool
    command_id: str
    status: CommandStatus
    message: str = ""
    error_code: Optional[str] = None
    task_request: Optional[TaskRequest] = None
    raw_text: str = ""
    normalized_text: str = ""


class RiskLevel(str, Enum):
    """Categorical risk classification for planned actions in accordance with Rule 21."""
    SAFE = "SAFE"        # Read-only observation, window enumeration
    LOW = "LOW"          # UI element focus, window activation, benign clicks
    MEDIUM = "MEDIUM"    # File rename, move, application launch, form fill
    HIGH = "HIGH"        # File deletion, overwrite, system preference modification
    BLOCKED = "BLOCKED"  # Shell execution, registry change, format disk, payment


class PlanStatus(str, Enum):
    """Lifecycle states of the AI Task Planner."""
    RECEIVED = "RECEIVED"
    CONTEXT_READY = "CONTEXT_READY"
    PLANNING = "PLANNING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ActionTarget:
    """Stable, coordinate-free target reference for UI or system objects."""
    target_type: str = "UI_ELEMENT"      # "UI_ELEMENT", "WINDOW", "FILE", "COORDINATE", "NONE"
    role: Optional[str] = None          # e.g., "Button", "Edit", "Window"
    name: Optional[str] = None          # Accessible name or file name
    automation_id: Optional[str] = None # UIA AutomationId if available
    window_title: Optional[str] = None  # Hosting window title
    element_id: Optional[str] = None    # Perception element_id reference
    coordinates: Optional[Dict[str, int]] = None  # Fallback only (e.g. {"x": 100, "y": 200})
    target_source: str = "UIA"          # "UIA", "OCR", "FILE_SYSTEM", "INFERRED"
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_type": self.target_type,
            "role": self.role,
            "name": self.name,
            "automation_id": self.automation_id,
            "window_title": self.window_title,
            "element_id": self.element_id,
            "coordinates": self.coordinates,
            "target_source": self.target_source,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionTarget":
        return cls(
            target_type=data.get("target_type", "UI_ELEMENT"),
            role=data.get("role"),
            name=data.get("name"),
            automation_id=data.get("automation_id"),
            window_title=data.get("window_title"),
            element_id=data.get("element_id"),
            coordinates=data.get("coordinates"),
            target_source=data.get("target_source", "UIA"),
            confidence=float(data.get("confidence", 1.0)),
        )


@dataclass
class ActionIntent:
    """Abstract representation of an intended capability invocation (NO direct execution)."""
    capability: str                     # Capability key (e.g., "CLICK_UI_ELEMENT", "MOVE_FILE")
    target: ActionTarget = field(default_factory=ActionTarget)
    parameters: Dict[str, Any] = field(default_factory=dict)  # Strictly data, NEVER code

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "target": self.target.to_dict(),
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionIntent":
        raw_target = data.get("target") or {}
        target_obj = ActionTarget.from_dict(raw_target) if isinstance(raw_target, dict) else ActionTarget()
        return cls(
            capability=data.get("capability", ""),
            target=target_obj,
            parameters=data.get("parameters", {}),
        )


@dataclass
class PlanStep:
    """Individual atomic step of a structured task plan."""
    step_id: str = field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    order: int = 1
    intent: ActionIntent = field(default_factory=lambda: ActionIntent(capability="OBSERVE_SCREEN"))
    description: str = ""
    preconditions: list[str] = field(default_factory=list)
    expected_result: str = ""
    verification_requirement: str = ""   # e.g., "CHECK_UI_ELEMENT_EXISTS", "CHECK_FILE_EXISTS"
    risk_level: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    requires_confirmation: bool = False
    depends_on: list[str] = field(default_factory=list)  # List of prerequisite step_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "order": self.order,
            "intent": self.intent.to_dict(),
            "description": self.description,
            "preconditions": self.preconditions,
            "expected_result": self.expected_result,
            "verification_requirement": self.verification_requirement,
            "risk_level": self.risk_level.value,
            "reversible": self.reversible,
            "requires_confirmation": self.requires_confirmation,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        raw_intent = data.get("intent") or {}
        intent_obj = ActionIntent.from_dict(raw_intent) if isinstance(raw_intent, dict) else ActionIntent(capability="OBSERVE_SCREEN")
        raw_risk = data.get("risk_level", "LOW")
        try:
            risk = RiskLevel(raw_risk)
        except ValueError:
            risk = RiskLevel.LOW
        return cls(
            step_id=data.get("step_id", f"step_{uuid.uuid4().hex[:8]}"),
            order=int(data.get("order", 1)),
            intent=intent_obj,
            description=data.get("description", ""),
            preconditions=list(data.get("preconditions", [])),
            expected_result=data.get("expected_result", ""),
            verification_requirement=data.get("verification_requirement", ""),
            risk_level=risk,
            reversible=bool(data.get("reversible", True)),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            depends_on=list(data.get("depends_on", [])),
        )


@dataclass
class TaskPlan:
    """Strongly typed, machine-readable task plan generated by the AI reasoning layer."""
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    command_id: str = ""
    task_id: str = ""
    goal: str = ""
    summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    requires_clarification: bool = False
    clarification_question: str = ""
    clarification_candidates: list[str] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
    expected_outcome: str = ""
    verification_requirements: list[str] = field(default_factory=list)
    planner_provider: str = "local"
    planner_model: str = "VisionPilot-Deterministic-Planner-v1"
    planner_runtime: str = "Rule-Engine / Deterministic SLM"
    accelerator: str = "CPU"
    status: PlanStatus = PlanStatus.READY
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "command_id": self.command_id,
            "task_id": self.task_id,
            "goal": self.goal,
            "summary": self.summary,
            "assumptions": self.assumptions,
            "requires_clarification": self.requires_clarification,
            "clarification_question": self.clarification_question,
            "clarification_candidates": self.clarification_candidates,
            "steps": [step.to_dict() for step in self.steps],
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "expected_outcome": self.expected_outcome,
            "verification_requirements": self.verification_requirements,
            "planner_provider": self.planner_provider,
            "planner_model": self.planner_model,
            "planner_runtime": self.planner_runtime,
            "accelerator": self.accelerator,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskPlan":
        raw_steps = data.get("steps", [])
        steps = [PlanStep.from_dict(s) for s in raw_steps if isinstance(s, dict)]
        raw_risk = data.get("risk_level", "SAFE")
        try:
            risk = RiskLevel(raw_risk)
        except ValueError:
            risk = RiskLevel.SAFE
        raw_status = data.get("status", "READY")
        try:
            status = PlanStatus(raw_status)
        except ValueError:
            status = PlanStatus.READY
        return cls(
            plan_id=data.get("plan_id", f"plan_{uuid.uuid4().hex[:12]}"),
            command_id=data.get("command_id", ""),
            task_id=data.get("task_id", ""),
            goal=data.get("goal", ""),
            summary=data.get("summary", ""),
            assumptions=list(data.get("assumptions", [])),
            requires_clarification=bool(data.get("requires_clarification", False)),
            clarification_question=data.get("clarification_question", ""),
            clarification_candidates=list(data.get("clarification_candidates", [])),
            steps=steps,
            risk_level=risk,
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            expected_outcome=data.get("expected_outcome", ""),
            verification_requirements=list(data.get("verification_requirements", [])),
            planner_provider=data.get("planner_provider", "local"),
            planner_model=data.get("planner_model", "VisionPilot-Deterministic-Planner-v1"),
            planner_runtime=data.get("planner_runtime", "Rule-Engine / Deterministic SLM"),
            accelerator=data.get("accelerator", "CPU"),
            status=status,
            metadata=data.get("metadata", {}),
        )

