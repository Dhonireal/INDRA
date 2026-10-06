"""
VisionPilot Recovery Manager.

Classifies action execution and verification failures, enforcing bounded, safe recovery policies:
- Prevents infinite retry loops via strict MAX_RECOVERY_DEPTH enforcement.
- Prohibits blind retries of side-effecting actions (e.g. Move file, Rename file).
- Enforces Human-in-the-Loop escalation (ASK_USER) on collisions and uncertain outcomes.
- Employs Re-perception before retrying UI actions.
- Emits structured RecoveryDecision models and RecoveryDecisionEvent audit records.
"""
from typing import Any, Dict, Optional, Tuple

from app.agent.task_schema import RiskLevel
from app.core.config import config
from app.core.events import event_bus, RecoveryDecisionEvent
from app.core.logger import logger
from app.execution.schema import ActionRequest, ActionResult, ActionStatus
from app.verification.schema import (
    RecoveryDecision, RecoveryDecisionType, VerificationResult,
    VerificationStatus
)


class RecoveryManager:
    """Evaluates failures and determines safe, bounded recovery strategies."""

    def __init__(self, max_recovery_depth: Optional[int] = None) -> None:
        self.max_recovery_depth = (
            max_recovery_depth
            if max_recovery_depth is not None
            else config.recovery.max_recovery_depth
        )
        self._action_attempt_counts: Dict[str, int] = {}

    def get_attempt_count(self, action_id: str) -> int:
        """Returns the number of recovery attempts already made for this action."""
        return self._action_attempt_counts.get(action_id, 0)

    def record_attempt(self, action_id: str) -> int:
        """Increments and returns the attempt count for an action."""
        current = self._action_attempt_counts.get(action_id, 0) + 1
        self._action_attempt_counts[action_id] = current
        return current

    def reset_attempts(self, action_id: Optional[str] = None) -> None:
        """Resets attempt counters."""
        if action_id:
            self._action_attempt_counts.pop(action_id, None)
        else:
            self._action_attempt_counts.clear()

    def evaluate_failure(
        self,
        action_req: ActionRequest,
        action_res: ActionResult,
        verif_res: Optional[VerificationResult] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> RecoveryDecision:
        """
        Evaluates failure telemetry and outputs a structured RecoveryDecision.
        Does NOT execute actions directly.
        """
        action_id = action_req.action_id
        task_id = action_req.task_id
        cap = action_req.capability
        attempts = self.get_attempt_count(action_id)

        # 1. Global Maximum Recovery Depth Check (Infinite Loop Prevention)
        if attempts >= self.max_recovery_depth:
            logger.warning(
                f"Action [{action_id}] reached max recovery depth ({attempts}/{self.max_recovery_depth}). Aborting."
            )
            decision = RecoveryDecision(
                decision=RecoveryDecisionType.ABORT,
                task_id=task_id,
                action_id=action_id,
                reason=f"Exceeded maximum recovery depth ({self.max_recovery_depth} attempts made).",
                attempts_made=attempts,
                max_attempts=self.max_recovery_depth,
                risk_level=action_req.risk_level,
            )
            self._emit_decision(decision)
            return decision

        # 2. Blocked by Safety Gate (Never retry blocked actions)
        if action_res.status == ActionStatus.BLOCKED:
            decision = RecoveryDecision(
                decision=RecoveryDecisionType.ABORT,
                task_id=task_id,
                action_id=action_id,
                reason=f"Action blocked by safety policy ({action_res.error_code}): {action_res.message}",
                attempts_made=attempts,
                max_attempts=self.max_recovery_depth,
                risk_level=action_req.risk_level,
            )
            self._emit_decision(decision)
            return decision

        # 3. User Cancellation or Confirmation Rejected
        if action_res.status == ActionStatus.CANCELLED or action_res.error_code in (
            "CONFIRMATION_REJECTED", "CONFIRMATION_EXPIRED"
        ):
            decision = RecoveryDecision(
                decision=RecoveryDecisionType.ABORT,
                task_id=task_id,
                action_id=action_id,
                reason="User cancelled action or rejected safety confirmation.",
                attempts_made=attempts,
                max_attempts=self.max_recovery_depth,
                risk_level=action_req.risk_level,
            )
            self._emit_decision(decision)
            return decision

        # 4. Side-Effecting Actions Policy (MOVE_FILE, RENAME_FILE, CREATE_FOLDER)
        # CRITICAL SAFETY RULE: Never blindly retry side-effecting actions.
        if cap in ("MOVE_FILE", "RENAME_FILE", "CREATE_FOLDER"):
            evidence = verif_res.evidence if verif_res else {}
            dest_exists = evidence.get("destination_exists", False)
            src_exists = evidence.get("source_exists", False)

            # Case A: Destination exists and source is absent -> Succeeded!
            if dest_exists and not src_exists:
                decision = RecoveryDecision(
                    decision=RecoveryDecisionType.RETRY,  # Treated as no-op verified
                    task_id=task_id,
                    action_id=action_id,
                    reason="Postcondition already satisfied.",
                    attempts_made=attempts,
                    max_attempts=self.max_recovery_depth,
                    risk_level=action_req.risk_level,
                )
                self._emit_decision(decision)
                return decision

            # Case B: Both exist -> Collision or partial copy -> ASK_USER
            if dest_exists and src_exists:
                decision = RecoveryDecision(
                    decision=RecoveryDecisionType.ASK_USER,
                    task_id=task_id,
                    action_id=action_id,
                    reason="File collision: both source and destination exist.",
                    attempts_made=attempts,
                    max_attempts=self.max_recovery_depth,
                    risk_level=action_req.risk_level,
                    parameters=evidence,
                )
                self._emit_decision(decision)
                return decision

            # Case C: Source exists and destination absent -> Safe single retry if below limit
            if src_exists and not dest_exists and attempts < 1:
                decision = RecoveryDecision(
                    decision=RecoveryDecisionType.RETRY,
                    task_id=task_id,
                    action_id=action_id,
                    reason=f"Safe retry: source file remains intact at {evidence.get('source_path')}.",
                    attempts_made=attempts,
                    max_attempts=1,
                    risk_level=action_req.risk_level,
                )
                self._emit_decision(decision)
                return decision

            # Otherwise, ask user or abort
            reason_msg = (
                f"Uncertain state: {verif_res.mismatch}"
                if (verif_res and verif_res.status == VerificationStatus.UNCERTAIN and verif_res.mismatch)
                else f"Filesystem action failed: {action_res.message}"
            )
            decision = RecoveryDecision(
                decision=RecoveryDecisionType.ASK_USER,
                task_id=task_id,
                action_id=action_id,
                reason=reason_msg,
                attempts_made=attempts,
                max_attempts=self.max_recovery_depth,
                risk_level=action_req.risk_level,
            )
            self._emit_decision(decision)
            return decision

        # 5. Handle Generic Uncertain Verification (e.g. indeterminate UI state)
        if verif_res and verif_res.status == VerificationStatus.UNCERTAIN:
            logger.info(f"Action [{action_id}] has UNCERTAIN verification result. Escalating to user.")
            decision = RecoveryDecision(
                decision=RecoveryDecisionType.ASK_USER,
                task_id=task_id,
                action_id=action_id,
                reason=f"Uncertain state: {verif_res.mismatch or 'Postcondition could not be conclusively verified.'}",
                attempts_made=attempts,
                max_attempts=self.max_recovery_depth,
                risk_level=action_req.risk_level,
                parameters={"mismatch": verif_res.mismatch, "evidence": verif_res.evidence},
            )
            self._emit_decision(decision)
            return decision


        # 6. UI Actions Policy (CLICK, DOUBLE_CLICK, TYPE_TEXT, SCROLL)
        if cap in ("CLICK_UI_ELEMENT", "DOUBLE_CLICK_UI_ELEMENT", "TYPE_TEXT", "SCROLL"):
            # Target not found or stale target -> Re-perceive first
            if action_res.error_code in ("TARGET_NOT_FOUND", "STALE_TARGET") or (
                verif_res and verif_res.status in (VerificationStatus.FAILED, VerificationStatus.TIMEOUT)
            ):
                if attempts < config.recovery.max_reperception_attempts:
                    decision = RecoveryDecision(
                        decision=RecoveryDecisionType.REPERCEIVE,
                        task_id=task_id,
                        action_id=action_id,
                        reason="Target missing or state unverified; re-perceiving screen state.",
                        attempts_made=attempts,
                        max_attempts=config.recovery.max_reperception_attempts,
                        risk_level=action_req.risk_level,
                    )
                    self._emit_decision(decision)
                    return decision
                elif attempts < config.recovery.max_ui_retries + config.recovery.max_reperception_attempts:
                    decision = RecoveryDecision(
                        decision=RecoveryDecisionType.RETRY,
                        task_id=task_id,
                        action_id=action_id,
                        reason="Retrying UI action after re-perception.",
                        attempts_made=attempts,
                        max_attempts=config.recovery.max_ui_retries,
                        risk_level=action_req.risk_level,
                    )
                    self._emit_decision(decision)
                    return decision
                else:
                    decision = RecoveryDecision(
                        decision=RecoveryDecisionType.ASK_USER,
                        task_id=task_id,
                        action_id=action_id,
                        reason=f"UI action failed after {attempts} attempts: {action_res.message}",
                        attempts_made=attempts,
                        max_attempts=self.max_recovery_depth,
                        risk_level=action_req.risk_level,
                    )
                    self._emit_decision(decision)
                    return decision

        # 7. Read-Only Actions Policy (OBSERVE_SCREEN, FIND_UI_ELEMENT, READ_FILE, FOCUS_WINDOW)
        if cap in ("OBSERVE_SCREEN", "FIND_UI_ELEMENT", "READ_FILE", "FOCUS_WINDOW"):
            if attempts < config.recovery.max_readonly_retries:
                decision = RecoveryDecision(
                    decision=RecoveryDecisionType.RETRY,
                    task_id=task_id,
                    action_id=action_id,
                    reason=f"Retrying read-only observation ({attempts + 1}/{config.recovery.max_readonly_retries}).",
                    attempts_made=attempts,
                    max_attempts=config.recovery.max_readonly_retries,
                    risk_level=RiskLevel.SAFE,
                )
                self._emit_decision(decision)
                return decision

        # 8. Default fallback: Mark Failed or Ask User
        decision = RecoveryDecision(
            decision=RecoveryDecisionType.MARK_FAILED,
            task_id=task_id,
            action_id=action_id,
            reason=f"Action unrecoverable: {action_res.message}",
            attempts_made=attempts,
            max_attempts=self.max_recovery_depth,
            risk_level=action_req.risk_level,
        )
        self._emit_decision(decision)
        return decision

    def _emit_decision(self, decision: RecoveryDecision) -> None:
        """Logs and publishes RecoveryDecisionEvent."""
        logger.info(
            f"Recovery Decision for [{decision.action_id}]: {decision.decision.value} "
            f"(attempt {decision.attempts_made}/{decision.max_attempts}) - {decision.reason}"
        )
        event_bus.publish(RecoveryDecisionEvent(
            decision_id=decision.decision_id,
            task_id=decision.task_id,
            action_id=decision.action_id,
            decision=decision.decision.value,
            reason=decision.reason,
            attempt=decision.attempts_made,
            max_attempts=decision.max_attempts,
            risk_level=decision.risk_level.value,
        ))


# Global recovery manager instance
recovery_manager = RecoveryManager()
