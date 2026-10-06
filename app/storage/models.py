"""
VisionPilot Storage Models and Audit Trail Schemas.

Defines strongly-typed dataclasses for persisting task lifecycle records,
plan metadata, action outcomes, verification postconditions, recovery events,
and append-only audit trails into SQLite.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class TaskRecord:
    """Persistent representation of a task lifecycle."""
    task_id: str
    user_command: str
    command_source: str = "text"
    status: str = "CREATED"
    command_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    final_outcome: Optional[str] = None
    error_code: Optional[str] = None
    error_message_redacted: Optional[str] = None
    cancellation_reason: Optional[str] = None
    plan_id: Optional[str] = None
    verification_status: Optional[str] = None
    recovery_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "command_id": self.command_id,
            "user_command": self.user_command,
            "command_source": self.command_source,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "final_outcome": self.final_outcome,
            "error_code": self.error_code,
            "error_message_redacted": self.error_message_redacted,
            "cancellation_reason": self.cancellation_reason,
            "plan_id": self.plan_id,
            "verification_status": self.verification_status,
            "recovery_count": self.recovery_count,
        }


@dataclass
class TaskPlanRecord:
    """Persistent metadata of a formulated task plan."""
    plan_id: str
    task_id: str
    provider: str
    model: str
    number_of_steps: int
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    planning_duration_ms: float = 0.0
    plan_validation_status: str = "VALID"
    risk_summary: str = "SAFE"
    goal: str = ""
    summary: str = ""
    steps_json: str = "[]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "provider": self.provider,
            "model": self.model,
            "number_of_steps": self.number_of_steps,
            "generated_at": self.generated_at,
            "planning_duration_ms": self.planning_duration_ms,
            "plan_validation_status": self.plan_validation_status,
            "risk_summary": self.risk_summary,
            "goal": self.goal,
            "summary": self.summary,
            "steps_json": self.steps_json,
        }


@dataclass
class ActionRecord:
    """Persistent record of an individual capability execution."""
    action_id: str
    task_id: str
    step_index: int
    capability: str
    action_type: str
    target_reference: str = ""
    risk_level: str = "SAFE"
    confirmation_required: bool = False
    confirmation_status: str = "NOT_REQUIRED"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    executor_status: str = "PENDING"
    result_status: Optional[str] = None
    error_code: Optional[str] = None
    error_message_redacted: Optional[str] = None
    parameters_redacted: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "task_id": self.task_id,
            "step_index": self.step_index,
            "capability": self.capability,
            "action_type": self.action_type,
            "target_reference": self.target_reference,
            "risk_level": self.risk_level,
            "confirmation_required": self.confirmation_required,
            "confirmation_status": self.confirmation_status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "executor_status": self.executor_status,
            "result_status": self.result_status,
            "error_code": self.error_code,
            "error_message_redacted": self.error_message_redacted,
            "parameters_redacted": self.parameters_redacted,
        }


@dataclass
class VerificationRecord:
    """Persistent record of postcondition verification."""
    verification_id: str
    task_id: str
    action_id: Optional[str]
    status: str
    verified: bool
    confidence: float
    strategy: str
    expected_state_summary: str = ""
    actual_state_summary: str = ""
    mismatch_summary: Optional[str] = None
    recovery_recommended: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "status": self.status,
            "verified": self.verified,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "expected_state_summary": self.expected_state_summary,
            "actual_state_summary": self.actual_state_summary,
            "mismatch_summary": self.mismatch_summary,
            "recovery_recommended": self.recovery_recommended,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
        }


@dataclass
class RecoveryRecord:
    """Persistent record of an attempted recovery intervention."""
    recovery_id: str
    task_id: str
    action_id: Optional[str]
    recovery_depth: int
    decision: str
    reason: str
    outcome: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "task_id": self.task_id,
            "action_id": self.action_id,
            "recovery_depth": self.recovery_depth,
            "decision": self.decision,
            "reason": self.reason,
            "outcome": self.outcome,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AuditRecord:
    """Append-only structured audit trail entry."""
    event_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    task_id: str = ""
    event_type: str = "AUDIT_EVENT"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL
    metadata_json: Dict[str, Any] = field(default_factory=dict)
    message_redacted: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "metadata_json": self.metadata_json,
            "message_redacted": self.message_redacted,
        }
