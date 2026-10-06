"""
VisionPilot Action Execution Domain Models.

Defines strongly typed models for:
- ActionStatus (PENDING, RUNNING, SUCCESS, FAILED, CANCELLED, TIMEOUT, BLOCKED, REQUIRES_CONFIRMATION, UNKNOWN_RESULT)
- ActionRequest (TaskPlan step converted to concrete execution request)
- ActionResult (Deterministic execution evidence and outcome)
- ConfirmationRequest & ConfirmationResult (Action-specific safety gate binding)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from app.agent.task_schema import ActionIntent, ActionTarget, RiskLevel


class ActionStatus(str, Enum):
    """Lifecycle and execution outcome status for individual computer actions."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    BLOCKED = "BLOCKED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"


@dataclass
class ActionRequest:
    """Strongly typed, validated execution request dispatched to ActionExecutor."""
    action_id: str = field(default_factory=lambda: f"act_{uuid.uuid4().hex[:10]}")
    task_id: str = ""
    step_id: str = ""
    step_order: int = 1
    capability: str = ""
    target: ActionTarget = field(default_factory=ActionTarget)
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 10.0
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    expected_result: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "step_order": self.step_order,
            "capability": self.capability,
            "target": self.target.to_dict(),
            "parameters": self.parameters,
            "timeout_seconds": self.timeout_seconds,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "expected_result": self.expected_result,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_plan_step(cls, task_id: str, step_dict: Dict[str, Any], default_timeout: float = 10.0) -> "ActionRequest":
        raw_intent = step_dict.get("intent", {})
        capability = raw_intent.get("capability", "")
        raw_target = raw_intent.get("target", {})
        target = ActionTarget.from_dict(raw_target) if isinstance(raw_target, dict) else ActionTarget()
        parameters = raw_intent.get("parameters", {})

        raw_risk = step_dict.get("risk_level", "LOW")
        try:
            risk = RiskLevel(raw_risk)
        except ValueError:
            risk = RiskLevel.LOW

        return cls(
            task_id=task_id,
            step_id=step_dict.get("step_id", ""),
            step_order=int(step_dict.get("order", 1)),
            capability=capability,
            target=target,
            parameters=parameters,
            timeout_seconds=default_timeout,
            risk_level=risk,
            requires_confirmation=bool(step_dict.get("requires_confirmation", False)),
            expected_result=step_dict.get("expected_result", ""),
        )


@dataclass
class ActionResult:
    """Structured, verifiable result returned upon completion of an ActionRequest."""
    action_id: str
    task_id: str
    capability: str
    status: ActionStatus = ActionStatus.PENDING
    success: bool = False
    message: str = ""
    error_code: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    target_description: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    reversible: bool = True
    rollback_available: bool = False

    def mark_completed(self, status: ActionStatus, message: str, evidence: Optional[Dict[str, Any]] = None, error_code: Optional[str] = None) -> None:
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000.0
        self.status = status
        self.success = (status == ActionStatus.SUCCESS)
        self.message = message
        self.error_code = error_code
        if evidence:
            self.evidence.update(evidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "task_id": self.task_id,
            "capability": self.capability,
            "status": self.status.value,
            "success": self.success,
            "message": self.message,
            "error_code": self.error_code,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": round(self.duration_ms, 2),
            "target_description": self.target_description,
            "evidence": self.evidence,
            "reversible": self.reversible,
            "rollback_available": self.rollback_available,
        }


@dataclass
class ConfirmationBinding:
    """Cryptographically tight or deterministic binding for safety confirmations."""
    confirmation_id: str = field(default_factory=lambda: f"conf_{uuid.uuid4().hex[:10]}")
    task_id: str = ""
    action_id: str = ""
    capability: str = ""
    target_summary: str = ""
    parameters_summary: str = ""
    risk_level: RiskLevel = RiskLevel.HIGH
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    is_resolved: bool = False
    is_approved: bool = False

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def matches(self, action_req: ActionRequest) -> bool:
        """Verifies that this confirmation belongs exactly to the requested action."""
        if self.is_expired():
            return False
        return (
            self.task_id == action_req.task_id and
            self.action_id == action_req.action_id and
            self.capability == action_req.capability
        )
