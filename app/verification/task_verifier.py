"""
VisionPilot Task-Level Verification Orchestrator.

Evaluates the holistic verification status of a completed or interrupted TaskPlan:
- Enforces strict Rule: Zero false success. A task is ONLY VERIFIED_SUCCESS if all steps are verified.
- Identifies PARTIALLY_COMPLETED tasks when earlier steps succeeded but a later step stopped.
- Identifies UNCERTAIN tasks when verification could not conclusively confirm postconditions.
- Identifies FAILED tasks when execution or verification failed unrecoverably.
- Generates structured TaskVerificationResult audit models.
"""
from typing import Any, Dict, List, Optional, Tuple

from app.agent.task_schema import PlanStep, TaskPlan
from app.core.logger import logger
from app.execution.schema import ActionResult, ActionStatus
from app.verification.schema import (
    TaskVerificationResult, VerificationResult, VerificationStatus
)


class TaskVerifier:
    """Evaluates multi-step TaskPlan execution and verification outcomes."""

    def evaluate_task_plan(
        self,
        plan: TaskPlan,
        step_executions: List[Tuple[ActionResult, Optional[VerificationResult]]],
    ) -> TaskVerificationResult:
        """
        Synthesizes execution and verification records into a final TaskVerificationResult.
        """
        total_steps = len(plan.steps) if plan and plan.steps else len(step_executions)
        verified_steps = 0
        step_records: List[Dict[str, Any]] = []

        has_uncertain = False
        has_failed = False
        has_blocked = False

        for idx, (action_res, verif_res) in enumerate(step_executions):
            step_desc = plan.steps[idx].description if (plan and idx < len(plan.steps)) else f"Step {idx + 1}"

            record = {
                "step_order": idx + 1,
                "description": step_desc,
                "action_id": action_res.action_id,
                "capability": action_res.capability,
                "action_status": action_res.status.value,
                "action_success": action_res.success,
                "verification_status": verif_res.status.value if verif_res else "NOT_VERIFIED",
                "verified": verif_res.verified if verif_res else False,
                "confidence": verif_res.confidence if verif_res else 0.0,
                "mismatch": verif_res.mismatch if verif_res else None,
            }
            step_records.append(record)

            if verif_res and verif_res.verified:
                verified_steps += 1
            elif verif_res and verif_res.status == VerificationStatus.UNCERTAIN:
                has_uncertain = True
            elif action_res.status == ActionStatus.BLOCKED:
                has_blocked = True
            elif not action_res.success or (verif_res and not verif_res.verified):
                has_failed = True

        task_id = plan.task_id if plan else (step_executions[0][0].task_id if step_executions else "")
        plan_id = plan.plan_id if plan else ""

        # Determine overall task status
        if total_steps > 0 and verified_steps == total_steps:
            status = "VERIFIED_SUCCESS"
            msg = f"Task verified successfully ({verified_steps}/{total_steps} steps confirmed)."
        elif has_uncertain:
            status = "UNCERTAIN"
            msg = f"Task outcome is uncertain ({verified_steps}/{total_steps} steps verified). Verification could not confirm final state."
        elif verified_steps > 0 and (has_failed or has_blocked or verified_steps < total_steps):
            status = "PARTIALLY_COMPLETED"
            msg = f"Task partially completed ({verified_steps}/{total_steps} steps verified before stopping)."
        elif has_blocked:
            status = "FAILED"
            msg = "Task halted because an action was blocked by safety policy."
        else:
            status = "FAILED"
            msg = f"Task failed ({verified_steps}/{total_steps} steps verified)."

        logger.info(f"Task Plan [{plan_id}] Final Verification: {status} - {msg}")

        return TaskVerificationResult(
            task_id=task_id,
            plan_id=plan_id,
            status=status,
            verified_steps=verified_steps,
            total_steps=total_steps,
            step_records=step_records,
            message=msg,
        )


# Global task verifier instance
task_verifier = TaskVerifier()
