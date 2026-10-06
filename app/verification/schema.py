"""
VisionPilot Action Verification & Recovery Data Models.

Defines strongly typed models for:
- ExpectedResultType & ExpectedResult (declarative postconditions)
- VerificationStatus & VerificationResult (evidence-based outcome)
- RecoveryDecisionType & RecoveryDecision (bounded recovery strategy)
- TaskVerificationResult (whole-plan verification status)
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from app.agent.task_schema import RiskLevel
from app.execution.schema import ActionRequest, ActionResult


class ExpectedResultType(str, Enum):
    """Supported declarative postcondition types for action verification."""
    UI_STATE = "UI_STATE"
    ELEMENT_PRESENT = "ELEMENT_PRESENT"
    ELEMENT_ABSENT = "ELEMENT_ABSENT"
    TEXT_PRESENT = "TEXT_PRESENT"
    TEXT_ABSENT = "TEXT_ABSENT"
    WINDOW_ACTIVE = "WINDOW_ACTIVE"
    FILE_EXISTS = "FILE_EXISTS"
    FILE_ABSENT = "FILE_ABSENT"
    FILE_MOVED = "FILE_MOVED"
    FILE_RENAMED = "FILE_RENAMED"
    VALUE_CHANGED = "VALUE_CHANGED"
    VALUE_EQUALS = "VALUE_EQUALS"
    CUSTOM_STRUCTURED_STATE = "CUSTOM_STRUCTURED_STATE"


class VerificationStatus(str, Enum):
    """Categorical verification outcomes."""
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


class VerificationConfidence:
    """Standardized verification confidence tiers."""
    STRONG = 1.0       # Exact UIA property or direct filesystem metadata assertion
    MEDIUM = 0.7       # Optical text match (OCR) or normalized comparison
    LOW = 0.4          # Heuristic fuzzy or approximate region match
    HEURISTIC = 0.2    # Partial evidence or temporal inference


@dataclass
class ExpectedResult:
    """Declared postcondition expected to hold after action execution."""
    expected_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:10]}")
    type: ExpectedResultType = ExpectedResultType.UI_STATE
    target: str = ""                         # Primary target (file path, element name, window title)
    secondary_target: Optional[str] = None   # Source path for move/rename, or parent window
    expected_value: Optional[Any] = None     # Expected text, control value, or file size
    timeout_seconds: float = 3.0
    poll_interval_seconds: float = 0.1
    stability_window_seconds: float = 0.2
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expected_id": self.expected_id,
            "type": self.type.value,
            "target": self.target,
            "secondary_target": self.secondary_target,
            "expected_value": self.expected_value,
            "timeout_seconds": self.timeout_seconds,
            "poll_interval_seconds": self.poll_interval_seconds,
            "stability_window_seconds": self.stability_window_seconds,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpectedResult":
        raw_type = data.get("type", "UI_STATE")
        try:
            exp_type = ExpectedResultType(raw_type)
        except ValueError:
            exp_type = ExpectedResultType.UI_STATE

        return cls(
            expected_id=data.get("expected_id", f"exp_{uuid.uuid4().hex[:10]}"),
            type=exp_type,
            target=data.get("target", ""),
            secondary_target=data.get("secondary_target"),
            expected_value=data.get("expected_value"),
            timeout_seconds=float(data.get("timeout_seconds", 3.0)),
            poll_interval_seconds=float(data.get("poll_interval_seconds", 0.1)),
            stability_window_seconds=float(data.get("stability_window_seconds", 0.2)),
            parameters=data.get("parameters", {}),
        )

    @classmethod
    def infer_from_action_request(cls, req: ActionRequest) -> "ExpectedResult":
        """Infers appropriate ExpectedResult postcondition from an ActionRequest."""
        cap = req.capability
        target_name = req.target.name or req.target.automation_id or ""
        params = req.parameters

        if cap == "CREATE_FOLDER":
            path = params.get("folder_path") or params.get("path") or target_name
            return cls(
                type=ExpectedResultType.FILE_EXISTS,
                target=path,
                expected_value="directory",
                parameters={"must_be_directory": True}
            )
        elif cap == "RENAME_FILE":
            src = params.get("source_path") or params.get("source") or params.get("path") or target_name
            new_name = params.get("new_name", "")
            return cls(
                type=ExpectedResultType.FILE_RENAMED,
                target=new_name,
                secondary_target=src,
                parameters={"source_path": src, "new_name": new_name}
            )
        elif cap == "MOVE_FILE":
            src = params.get("source_path") or params.get("source") or params.get("path") or target_name
            dest = params.get("destination_path") or params.get("destination", "")
            return cls(
                type=ExpectedResultType.FILE_MOVED,
                target=dest,
                secondary_target=src,
                parameters={"source_path": src, "destination_path": dest}
            )
        elif cap == "READ_FILE":
            path = params.get("file_path") or params.get("path") or target_name
            return cls(
                type=ExpectedResultType.FILE_EXISTS,
                target=path,
                parameters={"must_be_file": True}
            )
        elif cap in ("FOCUS_WINDOW", "SWITCH_WINDOW", "LAUNCH_APPLICATION"):
            title = params.get("app_name") or params.get("title") or target_name
            return cls(
                type=ExpectedResultType.WINDOW_ACTIVE,
                target=title,
                parameters={"window_title": title}
            )
        elif cap in ("FIND_FILE", "FIND_UI_ELEMENT", "OBSERVE_SCREEN", "SCROLL"):
            return cls(
                type=ExpectedResultType.CUSTOM_STRUCTURED_STATE,
                target=cap,
                parameters=params
            )
        elif cap in ("CLICK_UI_ELEMENT", "DOUBLE_CLICK_UI_ELEMENT"):
            return cls(
                type=ExpectedResultType.UI_STATE,
                target=target_name,
                parameters=params
            )
        elif cap == "TYPE_TEXT":
            expected_text = params.get("text", "")
            return cls(
                type=ExpectedResultType.VALUE_CHANGED,
                target=target_name,
                expected_value=expected_text,
                parameters=params
            )
        else:
            return cls(
                type=ExpectedResultType.UI_STATE,
                target=target_name,
                parameters=params
            )


@dataclass
class VerificationResult:
    """Structured, evidence-backed evaluation of an action's postcondition."""
    verification_id: str = field(default_factory=lambda: f"ver_{uuid.uuid4().hex[:10]}")
    task_id: str = ""
    action_id: str = ""
    status: VerificationStatus = VerificationStatus.UNCERTAIN
    verified: bool = False
    confidence: float = 0.0
    evidence: Dict[str, Any] = field(default_factory=dict)
    expected_state: Dict[str, Any] = field(default_factory=dict)
    actual_state: Dict[str, Any] = field(default_factory=dict)
    mismatch: Optional[str] = None
    strategy: str = ""
    recovery_recommended: bool = False
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_verified(self, strategy: str, confidence: float, evidence: Optional[Dict[str, Any]] = None) -> None:
        self.status = VerificationStatus.VERIFIED
        self.verified = True
        self.confidence = confidence
        self.strategy = strategy
        self.recovery_recommended = False
        self.mismatch = None
        if evidence:
            self.evidence.update(evidence)

    def mark_failed(self, strategy: str, mismatch: str, evidence: Optional[Dict[str, Any]] = None, recommend_recovery: bool = True) -> None:
        self.status = VerificationStatus.FAILED
        self.verified = False
        self.confidence = VerificationConfidence.STRONG
        self.strategy = strategy
        self.mismatch = mismatch
        self.recovery_recommended = recommend_recovery
        if evidence:
            self.evidence.update(evidence)

    def mark_uncertain(self, strategy: str, reason: str, evidence: Optional[Dict[str, Any]] = None) -> None:
        self.status = VerificationStatus.UNCERTAIN
        self.verified = False
        self.confidence = VerificationConfidence.LOW
        self.strategy = strategy
        self.mismatch = reason
        self.recovery_recommended = True
        if evidence:
            self.evidence.update(evidence)

    def mark_timeout(self, strategy: str, timeout_s: float, target_desc: str) -> None:
        self.status = VerificationStatus.TIMEOUT
        self.verified = False
        self.confidence = VerificationConfidence.STRONG
        self.strategy = strategy
        self.mismatch = f"Verification timed out after {timeout_s:.1f}s waiting for {target_desc}."
        self.recovery_recommended = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "status": self.status.value,
            "verified": self.verified,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "expected_state": self.expected_state,
            "actual_state": self.actual_state,
            "mismatch": self.mismatch,
            "strategy": self.strategy,
            "recovery_recommended": self.recovery_recommended,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp.isoformat(),
        }


class RecoveryDecisionType(str, Enum):
    """Categorical recovery decisions selected by RecoveryManager."""
    RETRY = "RETRY"                  # Re-attempt the action safely
    REPERCEIVE = "REPERCEIVE"        # Fresh scan of screen/UIA before proceeding
    REPLAN = "REPLAN"                # Structured replan request
    ASK_USER = "ASK_USER"            # Human-in-the-loop escalation / collision resolution
    ABORT = "ABORT"                  # Halt task immediately
    MARK_FAILED = "MARK_FAILED"      # Settle as failure (no recovery possible)
    MARK_UNCERTAIN = "MARK_UNCERTAIN"# Settle as uncertain postcondition


@dataclass
class RecoveryDecision:
    """Structured recovery policy decision emitted by RecoveryManager."""
    decision_id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:10]}")
    decision: RecoveryDecisionType = RecoveryDecisionType.ABORT
    task_id: str = ""
    action_id: str = ""
    reason: str = ""
    attempts_made: int = 0
    max_attempts: int = 3
    risk_level: RiskLevel = RiskLevel.LOW
    next_step: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "decision": self.decision.value,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "reason": self.reason,
            "attempts_made": self.attempts_made,
            "max_attempts": self.max_attempts,
            "risk_level": self.risk_level.value,
            "next_step": self.next_step,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class TaskVerificationResult:
    """Whole-plan verification status summarizing all step outcomes."""
    task_id: str
    plan_id: str
    status: str                         # VERIFIED_SUCCESS, PARTIALLY_COMPLETED, FAILED, UNCERTAIN
    verified_steps: int = 0
    total_steps: int = 0
    step_records: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "status": self.status,
            "verified_steps": self.verified_steps,
            "total_steps": self.total_steps,
            "step_records": self.step_records,
            "message": self.message,
            "completed_at": self.completed_at.isoformat(),
        }
