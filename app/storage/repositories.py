"""
VisionPilot Persistent Repositories.

Provides typed repository interfaces for tasks, plans, actions, verifications,
recoveries, audit events, and command history on top of SQLite.
All database operations are parameterized, transactional, and concurrency-safe.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from app.core.config import config
from app.core.logger import logger
from app.agent.task_schema import CommandRequest, CommandStatus
from app.storage.database import get_db, init_db
from app.storage.models import (
    TaskRecord, TaskPlanRecord, ActionRecord,
    VerificationRecord, RecoveryRecord, AuditRecord
)
from app.storage.redaction import PrivacyRedactor


class CommandRepository:
    """Repository for persisting and querying command history."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def save(self, cmd: CommandRequest, task_id: Optional[str] = None) -> None:
        """Inserts or updates a command record."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO command_history (
                        command_id, task_id, raw_text, normalized_text,
                        source, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cmd.command_id,
                    task_id or "",
                    PrivacyRedactor.redact_text(cmd.raw_text),
                    PrivacyRedactor.redact_text(cmd.normalized_text),
                    cmd.source.value,
                    cmd.status.value,
                    cmd.created_at.isoformat(),
                    cmd.updated_at.isoformat()
                ))
        except Exception as e:
            logger.warning(f"Failed to persist command {cmd.command_id}: {e}")

    def update_status(
        self,
        command_id: str,
        status: CommandStatus,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Updates the status and optional error details of a command."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE command_history
                    SET status = ?, error_code = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE command_id = ?
                """, (
                    status.value,
                    error_code,
                    PrivacyRedactor.redact_error(error_message or ""),
                    command_id
                ))
        except Exception as e:
            logger.warning(f"Failed to update command status for {command_id}: {e}")

    def get_by_id(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single command record by command_id."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM command_history WHERE command_id = ?", (command_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.warning(f"Failed to query command {command_id}: {e}")
        return None

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the most recent command records."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM command_history ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Failed to query recent commands: {e}")
            return []


class TaskRepository:
    """Repository for persisting, updating, querying, and retaining TaskRecords."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def save_task(self, task: TaskRecord) -> None:
        """Inserts or updates a task record."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (
                        task_id, command_id, user_command, command_source, status,
                        created_at, started_at, completed_at, duration_ms,
                        final_outcome, error_code, error_message_redacted,
                        cancellation_reason, plan_id, verification_status, recovery_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        command_id = excluded.command_id,
                        user_command = excluded.user_command,
                        command_source = excluded.command_source,
                        status = excluded.status,
                        started_at = COALESCE(excluded.started_at, tasks.started_at),
                        completed_at = COALESCE(excluded.completed_at, tasks.completed_at),
                        duration_ms = excluded.duration_ms,
                        final_outcome = COALESCE(excluded.final_outcome, tasks.final_outcome),
                        error_code = COALESCE(excluded.error_code, tasks.error_code),
                        error_message_redacted = COALESCE(excluded.error_message_redacted, tasks.error_message_redacted),
                        cancellation_reason = COALESCE(excluded.cancellation_reason, tasks.cancellation_reason),
                        plan_id = COALESCE(excluded.plan_id, tasks.plan_id),
                        verification_status = COALESCE(excluded.verification_status, tasks.verification_status),
                        recovery_count = excluded.recovery_count
                """, (
                    task.task_id,
                    task.command_id,
                    PrivacyRedactor.redact_text(task.user_command),
                    task.command_source,
                    task.status,
                    task.created_at,
                    task.started_at,
                    task.completed_at,
                    task.duration_ms,
                    task.final_outcome,
                    task.error_code,
                    PrivacyRedactor.redact_error(task.error_message_redacted or ""),
                    task.cancellation_reason,
                    task.plan_id,
                    task.verification_status,
                    task.recovery_count,
                ))
        except Exception as e:
            logger.error(f"Failed to persist task [{task.task_id}]: {e}")

    def update_plan_id(self, task_id: str, plan_id: str) -> None:
        """Updates plan_id for a task."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tasks SET plan_id = ? WHERE task_id = ?", (plan_id, task_id))
        except Exception as e:
            logger.warning(f"Failed to update plan_id for task [{task_id}]: {e}")

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Retrieves a task by task_id."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_task(row)
        except Exception as e:
            logger.error(f"Failed to query task [{task_id}]: {e}")
        return None

    def update_status(self, task_id: str, status: str, message: str = "") -> None:
        """Updates task status."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = ?
                    WHERE task_id = ?
                """, (status, task_id))
        except Exception as e:
            logger.warning(f"Failed to update task status for [{task_id}]: {e}")

    def complete_task(
        self,
        task_id: str,
        final_outcome: str,
        duration_ms: float,
        verification_status: str,
        status: str = "COMPLETED"
    ) -> None:
        """Marks a task as completed with outcome and verification metadata."""
        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = ?, completed_at = ?, duration_ms = ?,
                        final_outcome = ?, verification_status = ?
                    WHERE task_id = ?
                """, (status, completed_at, duration_ms, final_outcome, verification_status, task_id))
        except Exception as e:
            logger.error(f"Failed to complete task [{task_id}]: {e}")

    def fail_task(
        self,
        task_id: str,
        error_code: str,
        error_message: str,
        duration_ms: float
    ) -> None:
        """Marks a task as failed with sanitized error information."""
        completed_at = datetime.now(timezone.utc).isoformat()
        redacted_err = PrivacyRedactor.redact_error(error_message)
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = 'FAILED', completed_at = ?, duration_ms = ?,
                        error_code = ?, error_message_redacted = ?
                    WHERE task_id = ?
                """, (completed_at, duration_ms, error_code, redacted_err, task_id))
        except Exception as e:
            logger.error(f"Failed to record task failure for [{task_id}]: {e}")

    def cancel_task(self, task_id: str, reason: str, duration_ms: float = 0.0) -> None:
        """Marks a task as cancelled."""
        completed_at = datetime.now(timezone.utc).isoformat()
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = 'CANCELLED', completed_at = ?, duration_ms = ?, cancellation_reason = ?
                    WHERE task_id = ?
                """, (completed_at, duration_ms, reason, task_id))
        except Exception as e:
            logger.warning(f"Failed to record task cancellation for [{task_id}]: {e}")

    def mark_interrupted(self, task_id: str, reason: str) -> None:
        """Marks an unfinished task as INTERRUPTED due to unexpected shutdown or crash."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE tasks
                    SET status = 'INTERRUPTED', cancellation_reason = ?
                    WHERE task_id = ?
                """, (reason, task_id))
        except Exception as e:
            logger.warning(f"Failed to mark task [{task_id}] as interrupted: {e}")

    def get_interrupted_tasks(self) -> List[TaskRecord]:
        """Finds tasks left in non-terminal states from a previous application crash/session."""
        non_terminal = ("PLANNING", "WAITING_CONFIRMATION", "EXECUTING", "VERIFYING", "RECOVERING")
        placeholders = ",".join("?" for _ in non_terminal)
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM tasks WHERE status IN ({placeholders})", non_terminal)
                return [self._row_to_task(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"Failed to query interrupted tasks: {e}")
            return []

    def list_tasks(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[TaskRecord]:
        """Queries task records with optional filtering and search."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []

        if status and status != "ALL":
            query += " AND status = ?"
            params.append(status)

        if source and source != "ALL":
            query += " AND UPPER(command_source) = ?"
            params.append(source.upper())

        if search and search.strip():
            query += " AND user_command LIKE ?"
            params.append(f"%{search.strip()}%")

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [self._row_to_task(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return []

    def count_tasks(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        search: Optional[str] = None
    ) -> int:
        """Counts tasks matching the given filter criteria."""
        query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
        params: List[Any] = []

        if status and status != "ALL":
            query += " AND status = ?"
            params.append(status)

        if source and source != "ALL":
            query += " AND UPPER(command_source) = ?"
            params.append(source.upper())

        if search and search.strip():
            query += " AND user_command LIKE ?"
            params.append(f"%{search.strip()}%")

        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except Exception as e:
            logger.error(f"Failed to count tasks: {e}")
            return 0

    def delete_older_than(self, days: int) -> int:
        """Deletes terminal task records older than specified days."""
        if days <= 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        terminal_statuses = ("COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED", "PARTIALLY_COMPLETED")
        placeholders = ",".join("?" for _ in terminal_statuses)

        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    DELETE FROM tasks
                    WHERE created_at < ? AND status IN ({placeholders})
                """, [cutoff] + list(terminal_statuses))
                deleted = cursor.rowcount
                logger.info(f"Retention policy cleaned up {deleted} tasks older than {days} days")
                return deleted
        except Exception as e:
            logger.error(f"Failed to execute age-based history retention: {e}")
            return 0

    def enforce_max_count(self, max_tasks: int) -> int:
        """Ensures total stored tasks do not exceed max_tasks, removing oldest terminal tasks."""
        if max_tasks <= 0:
            return 0
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM tasks")
                total = cursor.fetchone()[0]
                if total <= max_tasks:
                    return 0

                excess = total - max_tasks
                terminal_statuses = ("COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED", "PARTIALLY_COMPLETED")
                placeholders = ",".join("?" for _ in terminal_statuses)

                cursor.execute(f"""
                    DELETE FROM tasks
                    WHERE task_id IN (
                        SELECT task_id FROM tasks
                        WHERE status IN ({placeholders})
                        ORDER BY created_at ASC
                        LIMIT ?
                    )
                """, list(terminal_statuses) + [excess])
                deleted = cursor.rowcount
                logger.info(f"Max-count retention policy pruned {deleted} tasks (limit: {max_tasks})")
                return deleted
        except Exception as e:
            logger.error(f"Failed to enforce max task count retention: {e}")
            return 0

    def clear_all_history(self) -> None:
        """Transactionally deletes all task history, plans, actions, verifications, recoveries, and audit events."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM audit_events")
                cursor.execute("DELETE FROM task_recoveries")
                cursor.execute("DELETE FROM task_verifications")
                cursor.execute("DELETE FROM task_actions")
                cursor.execute("DELETE FROM task_plans")
                cursor.execute("DELETE FROM tasks")
                cursor.execute("DELETE FROM command_history")
            logger.info("Cleared all persistent task history and audit events successfully.")
        except Exception as e:
            logger.error(f"Failed to clear task history: {e}")
            raise

    def _row_to_task(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            command_id=row["command_id"] or "",
            user_command=row["user_command"],
            command_source=row["command_source"],
            status=row["status"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=float(row["duration_ms"] or 0.0),
            final_outcome=row["final_outcome"],
            error_code=row["error_code"],
            error_message_redacted=row["error_message_redacted"],
            cancellation_reason=row["cancellation_reason"],
            plan_id=row["plan_id"],
            verification_status=row["verification_status"],
            recovery_count=int(row["recovery_count"] or 0),
        )


class TaskPlanRepository:
    """Repository for persisting and querying TaskPlanRecord."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def save_plan(self, plan: TaskPlanRecord) -> None:
        """Inserts or updates a task plan record."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO task_plans (
                        plan_id, task_id, provider, model, number_of_steps,
                        generated_at, planning_duration_ms, plan_validation_status,
                        risk_summary, goal, summary, steps_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan.plan_id,
                    plan.task_id,
                    plan.provider,
                    plan.model,
                    plan.number_of_steps,
                    plan.generated_at,
                    plan.planning_duration_ms,
                    plan.plan_validation_status,
                    plan.risk_summary,
                    PrivacyRedactor.redact_text(plan.goal),
                    PrivacyRedactor.redact_text(plan.summary),
                    plan.steps_json
                ))
        except Exception as e:
            logger.warning(f"Failed to persist plan [{plan.plan_id}]: {e}")

    def get_plan_by_task(self, task_id: str) -> Optional[TaskPlanRecord]:
        """Retrieves plan metadata for a task."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM task_plans WHERE task_id = ?", (task_id,))
                row = cursor.fetchone()
                if row:
                    return TaskPlanRecord(
                        plan_id=row["plan_id"],
                        task_id=row["task_id"],
                        provider=row["provider"],
                        model=row["model"],
                        number_of_steps=int(row["number_of_steps"]),
                        generated_at=row["generated_at"],
                        planning_duration_ms=float(row["planning_duration_ms"] or 0.0),
                        plan_validation_status=row["plan_validation_status"],
                        risk_summary=row["risk_summary"],
                        goal=row["goal"] or "",
                        summary=row["summary"] or "",
                        steps_json=row["steps_json"] or "[]"
                    )
        except Exception as e:
            logger.warning(f"Failed to query plan for task [{task_id}]: {e}")
        return None


class ActionRepository:
    """Repository for persisting and querying ActionRecord."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def save_action(self, action: ActionRecord) -> None:
        """Inserts or updates an action record with redacted parameters."""
        redacted_params = PrivacyRedactor.redact_action_parameters(
            action.capability, action.target_reference, action.parameters_redacted
        )
        params_json = json.dumps(redacted_params)
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO task_actions (
                        action_id, task_id, step_index, capability, action_type,
                        target_reference, risk_level, confirmation_required,
                        confirmation_status, started_at, completed_at, duration_ms,
                        executor_status, result_status, error_code,
                        error_message_redacted, parameters_redacted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    action.action_id,
                    action.task_id,
                    action.step_index,
                    action.capability,
                    action.action_type,
                    PrivacyRedactor.redact_text(action.target_reference),
                    action.risk_level,
                    1 if action.confirmation_required else 0,
                    action.confirmation_status,
                    action.started_at,
                    action.completed_at,
                    action.duration_ms,
                    action.executor_status,
                    action.result_status,
                    action.error_code,
                    PrivacyRedactor.redact_error(action.error_message_redacted or ""),
                    params_json
                ))
        except Exception as e:
            logger.warning(f"Failed to persist action [{action.action_id}]: {e}")

    def get_actions_for_task(self, task_id: str) -> List[ActionRecord]:
        """Retrieves all actions executed for a task ordered by step_index."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM task_actions WHERE task_id = ? ORDER BY step_index ASC", (task_id,))
                actions = []
                for row in cursor.fetchall():
                    params = json.loads(row["parameters_redacted"]) if row["parameters_redacted"] else {}
                    actions.append(ActionRecord(
                        action_id=row["action_id"],
                        task_id=row["task_id"],
                        step_index=int(row["step_index"]),
                        capability=row["capability"],
                        action_type=row["action_type"],
                        target_reference=row["target_reference"] or "",
                        risk_level=row["risk_level"],
                        confirmation_required=bool(row["confirmation_required"]),
                        confirmation_status=row["confirmation_status"],
                        started_at=row["started_at"],
                        completed_at=row["completed_at"],
                        duration_ms=float(row["duration_ms"] or 0.0),
                        executor_status=row["executor_status"],
                        result_status=row["result_status"],
                        error_code=row["error_code"],
                        error_message_redacted=row["error_message_redacted"],
                        parameters_redacted=params
                    ))
                return actions
        except Exception as e:
            logger.warning(f"Failed to query actions for task [{task_id}]: {e}")
            return []


class VerificationRepository:
    """Repository for persisting and querying VerificationRecord."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def save_verification(self, verif: VerificationRecord) -> None:
        """Inserts or updates a verification record."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO task_verifications (
                        verification_id, task_id, action_id, status, verified,
                        confidence, strategy, expected_state_summary,
                        actual_state_summary, mismatch_summary,
                        recovery_recommended, created_at, duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    verif.verification_id,
                    verif.task_id,
                    verif.action_id,
                    verif.status,
                    1 if verif.verified else 0,
                    verif.confidence,
                    verif.strategy,
                    PrivacyRedactor.redact_text(verif.expected_state_summary),
                    PrivacyRedactor.redact_text(verif.actual_state_summary),
                    PrivacyRedactor.redact_error(verif.mismatch_summary or ""),
                    1 if verif.recovery_recommended else 0,
                    verif.created_at,
                    verif.duration_ms
                ))
        except Exception as e:
            logger.warning(f"Failed to persist verification [{verif.verification_id}]: {e}")

    def get_verifications_for_task(self, task_id: str) -> List[VerificationRecord]:
        """Retrieves verifications associated with a task."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM task_verifications WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
                records = []
                for row in cursor.fetchall():
                    records.append(VerificationRecord(
                        verification_id=row["verification_id"],
                        task_id=row["task_id"],
                        action_id=row["action_id"],
                        status=row["status"],
                        verified=bool(row["verified"]),
                        confidence=float(row["confidence"] or 0.0),
                        strategy=row["strategy"],
                        expected_state_summary=row["expected_state_summary"] or "",
                        actual_state_summary=row["actual_state_summary"] or "",
                        mismatch_summary=row["mismatch_summary"],
                        recovery_recommended=bool(row["recovery_recommended"]),
                        created_at=row["created_at"],
                        duration_ms=float(row["duration_ms"] or 0.0)
                    ))
                return records
        except Exception as e:
            logger.warning(f"Failed to query verifications for task [{task_id}]: {e}")
            return []


class RecoveryRepository:
    """Repository for persisting and querying RecoveryRecord."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def save_recovery(self, rec: RecoveryRecord) -> None:
        """Inserts or updates a recovery record."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO task_recoveries (
                        recovery_id, task_id, action_id, recovery_depth,
                        decision, reason, outcome, created_at, duration_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec.recovery_id,
                    rec.task_id,
                    rec.action_id,
                    rec.recovery_depth,
                    rec.decision,
                    PrivacyRedactor.redact_text(rec.reason),
                    rec.outcome,
                    rec.created_at,
                    rec.duration_ms
                ))
        except Exception as e:
            logger.warning(f"Failed to persist recovery [{rec.recovery_id}]: {e}")

    def get_recoveries_for_task(self, task_id: str) -> List[RecoveryRecord]:
        """Retrieves recoveries for a task."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM task_recoveries WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
                records = []
                for row in cursor.fetchall():
                    records.append(RecoveryRecord(
                        recovery_id=row["recovery_id"],
                        task_id=row["task_id"],
                        action_id=row["action_id"],
                        recovery_depth=int(row["recovery_depth"]),
                        decision=row["decision"],
                        reason=row["reason"] or "",
                        outcome=row["outcome"],
                        created_at=row["created_at"],
                        duration_ms=float(row["duration_ms"] or 0.0)
                    ))
                return records
        except Exception as e:
            logger.warning(f"Failed to query recoveries for task [{task_id}]: {e}")
            return []


class AuditRepository:
    """Append-only audit trail repository."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or config.db_path
        init_db(self.db_path)

    def append_event(self, event: AuditRecord) -> None:
        """Appends an immutable audit event."""
        redacted_meta = PrivacyRedactor.redact_dict(event.metadata_json)
        meta_json = json.dumps(redacted_meta)
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_events (
                        event_id, task_id, event_type, timestamp,
                        severity, metadata_json, message_redacted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.task_id,
                    event.event_type,
                    event.timestamp,
                    event.severity,
                    meta_json,
                    PrivacyRedactor.redact_text(event.message_redacted)
                ))
        except Exception as e:
            logger.warning(f"Failed to append audit event [{event.event_id}]: {e}")

    def get_events_for_task(self, task_id: str) -> List[AuditRecord]:
        """Retrieves chronological audit events for a task."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_events WHERE task_id = ? ORDER BY timestamp ASC", (task_id,))
                records = []
                for row in cursor.fetchall():
                    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                    records.append(AuditRecord(
                        event_id=row["event_id"],
                        task_id=row["task_id"],
                        event_type=row["event_type"],
                        timestamp=row["timestamp"],
                        severity=row["severity"],
                        metadata_json=meta,
                        message_redacted=row["message_redacted"] or ""
                    ))
                return records
        except Exception as e:
            logger.warning(f"Failed to query audit events for task [{task_id}]: {e}")
            return []

    def get_recent_events(self, limit: int = 100) -> List[AuditRecord]:
        """Retrieves the most recent audit events across all tasks."""
        try:
            with get_db(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (limit,))
                records = []
                for row in cursor.fetchall():
                    meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
                    records.append(AuditRecord(
                        event_id=row["event_id"],
                        task_id=row["task_id"],
                        event_type=row["event_type"],
                        timestamp=row["timestamp"],
                        severity=row["severity"],
                        metadata_json=meta,
                        message_redacted=row["message_redacted"] or ""
                    ))
                return records
        except Exception as e:
            logger.warning(f"Failed to query recent audit events: {e}")
            return []


# Global repository instances
command_repository = CommandRepository()
task_repository = TaskRepository()
plan_repository = TaskPlanRepository()
action_repository = ActionRepository()
verification_repository = VerificationRepository()
recovery_repository = RecoveryRepository()
audit_repository = AuditRepository()
