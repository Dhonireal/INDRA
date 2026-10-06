"""
VisionPilot Task History and Audit Trail Service.

Orchestrates persistence of user commands, task lifecycles, generated plan metadata,
actions, verifications, recoveries, safety confirmation events, and immutable audit logs.
Includes startup crash recovery, privacy redaction, and deterministic history retention.
"""
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import config
from app.core.logger import logger
from app.core.events import (
    event_bus, CommandReceivedEvent, TaskCreatedEvent, TaskStatusChangedEvent,
    PlanGeneratedEvent, SafetyConfirmationRequiredEvent, SafetyConfirmationResolvedEvent,
    ActionRequestedEvent, ActionExecutedEvent, ActionBlockedEvent,
    VerificationStartedEvent, VerificationCompletedEvent,
    RecoveryDecisionEvent, RecoveryAttemptedEvent,
    TaskCompletedEvent, TaskFailedEvent, TaskCancelledEvent, TaskInterruptedEvent,
    ErrorEvent
)
from app.storage.models import (
    TaskRecord, TaskPlanRecord, ActionRecord,
    VerificationRecord, RecoveryRecord, AuditRecord
)
from app.storage.repositories import (
    TaskRepository, TaskPlanRepository, ActionRepository,
    VerificationRepository, RecoveryRepository, AuditRepository,
    task_repository, plan_repository, action_repository,
    verification_repository, recovery_repository, audit_repository
)
from app.storage.redaction import PrivacyRedactor


class TaskHistoryService:
    """Central service managing task history, audit trails, and startup recovery."""

    def __init__(
        self,
        task_repo: Optional[TaskRepository] = None,
        plan_repo: Optional[TaskPlanRepository] = None,
        action_repo: Optional[ActionRepository] = None,
        verif_repo: Optional[VerificationRepository] = None,
        rec_repo: Optional[RecoveryRepository] = None,
        audit_repo: Optional[AuditRepository] = None,
    ) -> None:
        self.task_repo = task_repo or task_repository
        self.plan_repo = plan_repo or plan_repository
        self.action_repo = action_repo or action_repository
        self.verif_repo = verif_repo or verification_repository
        self.rec_repo = rec_repo or recovery_repository
        self.audit_repo = audit_repo or audit_repository

        self._lock = threading.Lock()
        self._action_start_times: Dict[str, float] = {}
        self._subscribed = False

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """Connects domain lifecycle events to persistent history recording."""
        if self._subscribed:
            return

        event_bus.subscribe(CommandReceivedEvent, self._on_command_received)
        event_bus.subscribe(TaskCreatedEvent, self._on_task_created)
        event_bus.subscribe(TaskStatusChangedEvent, self._on_task_status_changed)
        event_bus.subscribe(PlanGeneratedEvent, self._on_plan_generated)
        event_bus.subscribe(SafetyConfirmationRequiredEvent, self._on_confirmation_required)
        event_bus.subscribe(SafetyConfirmationResolvedEvent, self._on_confirmation_resolved)
        event_bus.subscribe(ActionRequestedEvent, self._on_action_requested)
        event_bus.subscribe(ActionExecutedEvent, self._on_action_executed)
        event_bus.subscribe(ActionBlockedEvent, self._on_action_blocked)
        event_bus.subscribe(VerificationStartedEvent, self._on_verification_started)
        event_bus.subscribe(VerificationCompletedEvent, self._on_verification_completed)
        event_bus.subscribe(RecoveryDecisionEvent, self._on_recovery_decision)
        event_bus.subscribe(RecoveryAttemptedEvent, self._on_recovery_attempted)
        event_bus.subscribe(TaskCompletedEvent, self._on_task_completed)
        event_bus.subscribe(TaskFailedEvent, self._on_task_failed)
        event_bus.subscribe(TaskCancelledEvent, self._on_task_cancelled)
        event_bus.subscribe(TaskInterruptedEvent, self._on_task_interrupted)
        event_bus.subscribe(ErrorEvent, self._on_error_event)

        self._subscribed = True

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    def _on_command_received(self, ev: CommandReceivedEvent) -> None:
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.command_id,
            event_type="COMMAND_RECEIVED",
            severity="INFO",
            metadata_json={"source": ev.source},
            message_redacted=f"Command received via {ev.source}: '{PrivacyRedactor.redact_text(ev.raw_text)}'"
        ))

    def _on_task_created(self, ev: TaskCreatedEvent) -> None:
        task = TaskRecord(
            task_id=ev.task_id,
            user_command=ev.command,
            command_source=ev.source,
            status="CREATED",
            started_at=datetime.now(timezone.utc).isoformat()
        )
        self.task_repo.save_task(task)
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="TASK_CREATED",
            severity="INFO",
            metadata_json={"source": ev.source},
            message_redacted=f"Task [{ev.task_id}] created for command: '{PrivacyRedactor.redact_text(ev.command)}'"
        ))

    def _on_task_status_changed(self, ev: TaskStatusChangedEvent) -> None:
        self.task_repo.update_status(ev.task_id, ev.new_status, ev.message)
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="TASK_STATUS_CHANGED",
            severity="INFO",
            metadata_json={"old_status": ev.old_status, "new_status": ev.new_status},
            message_redacted=f"Task transitioned from {ev.old_status} to {ev.new_status}: {ev.message}"
        ))

    def _ensure_task_exists(self, task_id: str, default_command: str = "", default_status: str = "EXECUTING") -> None:
        """Ensures a parent task row exists before child foreign-key operations."""
        if not task_id:
            return
        if not self.task_repo.get_task(task_id):
            cmd = default_command or f"Task [{task_id}]"
            self.task_repo.save_task(TaskRecord(
                task_id=task_id,
                user_command=cmd,
                status=default_status
            ))

    def _on_plan_generated(self, ev: PlanGeneratedEvent) -> None:
        self._ensure_task_exists(ev.task_id, default_command=ev.goal or f"Task [{ev.task_id}]", default_status="PLANNING")
        plan_rec = TaskPlanRecord(
            plan_id=ev.plan_id,
            task_id=ev.task_id,
            provider=ev.provider or "local",
            model=ev.model or "Deterministic-Planner",
            number_of_steps=ev.step_count,
            plan_validation_status="VALID",
            risk_summary=ev.risk_level,
            goal=ev.goal,
            summary=ev.summary,
            steps_json=json.dumps(ev.steps) if ev.steps else "[]"
        )
        self.plan_repo.save_plan(plan_rec)

        # Update task with plan_id
        self.task_repo.update_plan_id(ev.task_id, ev.plan_id)

        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="PLAN_CREATED",
            severity="INFO",
            metadata_json={
                "plan_id": ev.plan_id,
                "step_count": ev.step_count,
                "risk_level": ev.risk_level,
                "requires_confirmation": ev.requires_confirmation
            },
            message_redacted=f"Plan generated with {ev.step_count} steps (Risk: {ev.risk_level})"
        ))

    def _on_confirmation_required(self, ev: SafetyConfirmationRequiredEvent) -> None:
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="CONFIRMATION_REQUESTED",
            severity="WARNING",
            metadata_json={
                "action_id": ev.action_id,
                "action_type": ev.action_type,
                "target": ev.target,
                "risk_level": ev.risk_level
            },
            message_redacted=f"User confirmation requested for {ev.action_type} on target '{ev.target}'"
        ))

    def _on_confirmation_resolved(self, ev: SafetyConfirmationResolvedEvent) -> None:
        event_name = "CONFIRMATION_GRANTED" if ev.approved else "CONFIRMATION_DENIED"
        severity = "INFO" if ev.approved else "WARNING"
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type=event_name,
            severity=severity,
            metadata_json={"action_id": ev.action_id, "approved": ev.approved},
            message_redacted=f"Confirmation {'GRANTED' if ev.approved else 'DENIED'}: {ev.reason}"
        ))

    def _on_action_requested(self, ev: ActionRequestedEvent) -> None:
        self._ensure_task_exists(ev.task_id, default_command=f"Action on {ev.target}", default_status="EXECUTING")
        action_rec = ActionRecord(
            action_id=ev.action_id,
            task_id=ev.task_id,
            step_index=ev.step_index,
            capability=ev.capability,
            action_type=ev.action_type,
            target_reference=ev.target,
            risk_level=ev.risk_level,
            confirmation_required=ev.requires_confirmation,
            started_at=datetime.now(timezone.utc).isoformat(),
            executor_status="EXECUTING",
            parameters_redacted=ev.parameters
        )
        self.action_repo.save_action(action_rec)

        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="ACTION_STARTED",
            severity="INFO",
            metadata_json={
                "action_id": ev.action_id,
                "step_index": ev.step_index,
                "capability": ev.capability
            },
            message_redacted=f"Action step {ev.step_index + 1} started: {ev.capability} ({ev.target})"
        ))

    def _on_action_executed(self, ev: ActionExecutedEvent) -> None:
        actions = self.action_repo.get_actions_for_task(ev.task_id)
        action_rec = next((a for a in actions if a.action_id == ev.action_id), None)
        if not action_rec:
            action_rec = ActionRecord(
                action_id=ev.action_id,
                task_id=ev.task_id,
                step_index=ev.step_index,
                capability=ev.capability,
                action_type=ev.action_type,
                risk_level="SAFE"
            )

        action_rec.completed_at = datetime.now(timezone.utc).isoformat()
        action_rec.duration_ms = ev.duration_ms
        action_rec.executor_status = ev.status
        action_rec.result_status = "SUCCESS" if ev.success else "FAILED"
        action_rec.error_code = ev.error_code
        action_rec.error_message_redacted = ev.result_details if not ev.success else None
        self.action_repo.save_action(action_rec)

        event_type = "ACTION_COMPLETED" if ev.success else "ACTION_FAILED"
        severity = "INFO" if ev.success else "ERROR"
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type=event_type,
            severity=severity,
            metadata_json={
                "action_id": ev.action_id,
                "success": ev.success,
                "duration_ms": ev.duration_ms,
                "error_code": ev.error_code
            },
            message_redacted=f"Action step {ev.step_index + 1} {event_type.lower()}: {ev.status} ({ev.duration_ms:.1f}ms)"
        ))

    def _on_action_blocked(self, ev: ActionBlockedEvent) -> None:
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="ACTION_BLOCKED",
            severity="WARNING",
            metadata_json={"action_id": ev.action_id, "capability": ev.capability, "error_code": ev.error_code},
            message_redacted=f"Action blocked by safety policy: {ev.reason}"
        ))

    def _on_verification_started(self, ev: VerificationStartedEvent) -> None:
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="VERIFICATION_STARTED",
            severity="INFO",
            metadata_json={
                "verification_id": ev.verification_id,
                "action_id": ev.action_id,
                "strategy": ev.strategy,
                "expected_type": ev.expected_type
            },
            message_redacted=f"Verification started using {ev.strategy} for expected postcondition: {ev.expected_type}"
        ))

    def _on_verification_completed(self, ev: VerificationCompletedEvent) -> None:
        self._ensure_task_exists(ev.task_id, default_command=f"Verification for {ev.action_id}", default_status="VERIFYING")
        verif_rec = VerificationRecord(
            verification_id=ev.verification_id,
            task_id=ev.task_id,
            action_id=ev.action_id,
            status=ev.status,
            verified=ev.verified,
            confidence=ev.confidence,
            strategy=ev.strategy,
            expected_state_summary=ev.expected,
            actual_state_summary=ev.observed,
            mismatch_summary=ev.mismatch,
            recovery_recommended=ev.recovery_recommended,
            duration_ms=ev.duration_ms
        )
        self.verif_repo.save_verification(verif_rec)

        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="VERIFICATION_COMPLETED",
            severity="INFO" if ev.verified else "WARNING",
            metadata_json={
                "verification_id": ev.verification_id,
                "status": ev.status,
                "verified": ev.verified,
                "confidence": ev.confidence
            },
            message_redacted=f"Verification completed: status={ev.status}, verified={ev.verified}, confidence={ev.confidence:.2f}"
        ))

    def _on_recovery_decision(self, ev: RecoveryDecisionEvent) -> None:
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="RECOVERY_DECISION",
            severity="WARNING",
            metadata_json={
                "decision": ev.decision,
                "attempt": ev.attempt,
                "max_attempts": ev.max_attempts
            },
            message_redacted=f"Recovery decision: {ev.decision} (Attempt {ev.attempt}/{ev.max_attempts}): {ev.reason}"
        ))

    def _on_recovery_attempted(self, ev: RecoveryAttemptedEvent) -> None:
        self._ensure_task_exists(ev.task_id, default_command=f"Recovery for {ev.action_id}", default_status="RECOVERING")
        rec = RecoveryRecord(
            recovery_id=f"rec_{datetime.now(timezone.utc).strftime('%H%M%S%f')}",
            task_id=ev.task_id,
            action_id=ev.action_id,
            recovery_depth=ev.attempt_number,
            decision=ev.strategy,
            reason=f"Recovery attempt #{ev.attempt_number}",
            outcome=ev.outcome
        )
        self.rec_repo.save_recovery(rec)

        # Update recovery count on task
        task = self.task_repo.get_task(ev.task_id)
        if task:
            task.recovery_count = max(task.recovery_count, ev.attempt_number)
            self.task_repo.save_task(task)

        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="RECOVERY_COMPLETED",
            severity="INFO" if ev.outcome == "SUCCESS" else "WARNING",
            metadata_json={
                "attempt": ev.attempt_number,
                "strategy": ev.strategy,
                "outcome": ev.outcome
            },
            message_redacted=f"Recovery attempt #{ev.attempt_number} ({ev.strategy}) finished with outcome: {ev.outcome}"
        ))

    def _on_task_completed(self, ev: TaskCompletedEvent) -> None:
        self.task_repo.complete_task(
            task_id=ev.task_id,
            final_outcome=ev.final_outcome,
            duration_ms=ev.duration_ms,
            verification_status=ev.verification_status,
            status=ev.status
        )
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="TASK_COMPLETED",
            severity="INFO",
            metadata_json={
                "status": ev.status,
                "verification_status": ev.verification_status,
                "duration_ms": ev.duration_ms
            },
            message_redacted=f"Task completed with status {ev.status} ({ev.duration_ms:.1f}ms): {ev.final_outcome}"
        ))
        self.cleanup_retention()

    def _on_task_failed(self, ev: TaskFailedEvent) -> None:
        self.task_repo.fail_task(
            task_id=ev.task_id,
            error_code=ev.error_code,
            error_message=ev.error_message,
            duration_ms=ev.duration_ms
        )
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="TASK_FAILED",
            severity="ERROR",
            metadata_json={"error_code": ev.error_code, "duration_ms": ev.duration_ms},
            message_redacted=f"Task failed ({ev.error_code}): {PrivacyRedactor.redact_error(ev.error_message)}"
        ))
        self.cleanup_retention()

    def _on_task_cancelled(self, ev: TaskCancelledEvent) -> None:
        self.task_repo.cancel_task(
            task_id=ev.task_id,
            reason=ev.reason,
            duration_ms=ev.duration_ms
        )
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="TASK_CANCELLED",
            severity="WARNING",
            metadata_json={"reason": ev.reason},
            message_redacted=f"Task cancelled: {ev.reason}"
        ))
        self.cleanup_retention()

    def _on_task_interrupted(self, ev: TaskInterruptedEvent) -> None:
        self.task_repo.mark_interrupted(ev.task_id, ev.reason)
        self.audit_repo.append_event(AuditRecord(
            task_id=ev.task_id,
            event_type="TASK_INTERRUPTED",
            severity="WARNING",
            metadata_json={"reason": ev.reason},
            message_redacted=f"Task interrupted: {ev.reason}"
        ))

    def _on_error_event(self, ev: ErrorEvent) -> None:
        if ev.task_id:
            self.audit_repo.append_event(AuditRecord(
                task_id=ev.task_id,
                event_type="SYSTEM_ERROR",
                severity="ERROR",
                metadata_json={"recoverable": ev.recoverable},
                message_redacted=PrivacyRedactor.redact_error(ev.user_message)
            ))

    # --------------------------------------------------------------------------
    # Startup Recovery & Retention Policies
    # --------------------------------------------------------------------------

    def recover_interrupted_tasks(self) -> List[TaskRecord]:
        """
        Inspects the database for tasks left in unfinished states from a prior abnormal shutdown.
        Marks them as INTERRUPTED and appends an audit event.
        STRICT REQUIREMENT: Does NOT resume side-effecting actions automatically.
        """
        interrupted = self.task_repo.get_interrupted_tasks()
        if interrupted:
            logger.warning(f"Detected {len(interrupted)} interrupted task(s) from prior session.")
            for task in interrupted:
                reason = "Execution was interrupted by application shutdown or crash. Not resumed automatically."
                self.task_repo.mark_interrupted(task.task_id, reason)
                self.audit_repo.append_event(AuditRecord(
                    task_id=task.task_id,
                    event_type="TASK_INTERRUPTED",
                    severity="WARNING",
                    metadata_json={"previous_status": task.status},
                    message_redacted=reason
                ))
                task.status = "INTERRUPTED"
                task.cancellation_reason = reason
        else:
            logger.debug("Startup audit: No interrupted tasks found.")
        return interrupted

    def cleanup_retention(self) -> Dict[str, int]:
        """
        Executes deterministic retention pruning based on config:
        1. Deletes records older than retention_days.
        2. Enforces max_tasks ceiling.
        """
        if not config.history.enabled:
            return {"deleted_by_age": 0, "deleted_by_max_count": 0}

        deleted_age = 0
        if config.history.retention_days > 0:
            deleted_age = self.task_repo.delete_older_than(config.history.retention_days)

        deleted_max = 0
        if config.history.max_tasks > 0:
            deleted_max = self.task_repo.enforce_max_count(config.history.max_tasks)

        return {"deleted_by_age": deleted_age, "deleted_by_max_count": deleted_max}

    def clear_history(self) -> None:
        """
        Safely clears all persistent task history, plans, actions, verifications,
        recoveries, and audit records. Requires explicit confirmation at the UI layer.
        """
        self.task_repo.clear_all_history()

    # --------------------------------------------------------------------------
    # Queries & Aggregation
    # --------------------------------------------------------------------------

    def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Aggregates comprehensive, redacted task execution details for the UI."""
        task = self.task_repo.get_task(task_id)
        if not task:
            return None

        plan = self.plan_repo.get_plan_by_task(task_id)
        actions = self.action_repo.get_actions_for_task(task_id)
        verifications = self.verif_repo.get_verifications_for_task(task_id)
        recoveries = self.rec_repo.get_recoveries_for_task(task_id)
        audit_events = self.audit_repo.get_events_for_task(task_id)

        return {
            "task": task.to_dict(),
            "plan": plan.to_dict() if plan else None,
            "actions": [a.to_dict() for a in actions],
            "verifications": [v.to_dict() for v in verifications],
            "recoveries": [r.to_dict() for r in recoveries],
            "audit_events": [e.to_dict() for e in audit_events],
        }

    def list_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[TaskRecord]:
        """Queries tasks with filtering."""
        return self.task_repo.list_tasks(limit=limit, offset=offset, status=status, source=source, search=search)

    def count_tasks(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
        """Counts tasks matching the given filter criteria."""
        return self.task_repo.count_tasks(status=status, source=source, search=search)


# Global service instance and aliases
TaskHistoryService_Alias = TaskHistoryService
HistoryService = TaskHistoryService
history_service = TaskHistoryService()
