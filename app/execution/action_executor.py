"""
VisionPilot Action Executor Engine.

Orchestrates sequential, observable execution of validated TaskPlans:
- Converts PlanSteps into ActionRequests
- Evaluates actions through ActionSafetyGate
- Enforces Human-in-the-Loop Confirmation when required
- Dispatches to specialized capability executors:
  - UIActionExecutor (clicks, double-clicks, scrolls, observations)
  - KeyboardActionExecutor (text typing, key press, allowlisted hotkeys)
  - WindowActionExecutor (focus window, allowlisted application launch)
  - FileActionExecutor (find, read, create folder, rename, move)
- Prevents duplicate action execution (Action Locking)
- Handles user cancellation and action timeouts
- Updates AppState and publishes ActionExecutedEvent audit records
"""
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path

from app.agent.capabilities import CapabilityRegistry, capability_registry
from app.agent.task_schema import PlanStatus, TaskPlan
from app.core.config import config
from app.core.events import (
    event_bus, ActionBlockedEvent, ActionExecutedEvent,
    ActionRequestedEvent, TaskStatusChangedEvent,
    TaskCompletedEvent, TaskFailedEvent, TaskCancelledEvent
)
from app.core.logger import logger
from app.core.state import app_state, TaskStatus
from app.execution.file_executor import FileActionExecutor
from app.execution.keyboard_executor import KeyboardActionExecutor
from app.execution.safety_gate import ActionSafetyGate, action_safety_gate
from app.execution.schema import ActionRequest, ActionResult, ActionStatus
from app.execution.ui_executor import UIActionExecutor
from app.execution.window_executor import WindowActionExecutor
from app.verification.engine import VerificationEngine, verification_engine
from app.verification.recovery import RecoveryManager, recovery_manager
from app.verification.schema import (
    RecoveryDecisionType, TaskVerificationResult, VerificationResult,
    VerificationStatus
)
from app.verification.strategies.registry import VerificationStrategyRegistry
from app.verification.task_verifier import TaskVerifier, task_verifier


class ActionExecutor:
    """Master orchestrator converting structured TaskPlans into safe computer actions with verification and recovery."""

    def __init__(
        self,
        safety_gate: Optional[ActionSafetyGate] = None,
        ui_exec: Optional[UIActionExecutor] = None,
        kb_exec: Optional[KeyboardActionExecutor] = None,
        win_exec: Optional[WindowActionExecutor] = None,
        file_exec: Optional[FileActionExecutor] = None,
        verif_engine: Optional[VerificationEngine] = None,
        rec_manager: Optional[RecoveryManager] = None,
        task_verif: Optional[TaskVerifier] = None,
    ) -> None:
        self.safety_gate = safety_gate or action_safety_gate
        self.ui_executor = ui_exec or UIActionExecutor()
        self.keyboard_executor = kb_exec or KeyboardActionExecutor()
        self.window_executor = win_exec or WindowActionExecutor()
        self.file_executor = file_exec or FileActionExecutor()
        if verif_engine is not None:
            self.verification_engine = verif_engine
        elif file_exec is not None:
            self.verification_engine = VerificationEngine(
                registry=VerificationStrategyRegistry(path_policy=self.file_executor.policy)
            )
        else:
            self.verification_engine = verification_engine
        self.recovery_manager = rec_manager or recovery_manager
        self.task_verifier = task_verif or task_verifier

        self._lock = threading.Lock()
        self._completed_action_ids: Set[str] = set()
        self._is_cancelled = False
        self._execution_history: List[ActionResult] = []
        self.step_verifications: List[Tuple[ActionResult, Optional[VerificationResult]]] = []
        self.last_task_verification: Optional[TaskVerificationResult] = None

    def execute_plan(self, plan: TaskPlan) -> List[ActionResult]:
        """
        Executes a validated TaskPlan sequentially step-by-step.
        Returns the list of ActionResults for each step.
        """
        if not plan or plan.status != PlanStatus.READY or not plan.steps:
            logger.warning(f"Rejected unvalidated or empty plan [{plan.plan_id if plan else 'None'}]")
            return []

        # Reset task-local execution state at the start of a NEW plan execution
        with self._lock:
            self._is_cancelled = False
            self.step_verifications.clear()
            self._completed_action_ids.clear()

        task_id = plan.task_id or f"task_{plan.plan_id}"
        total_steps = len(plan.steps)
        logger.info(f"Starting controlled execution of plan [{plan.plan_id}] ({total_steps} steps)")
        app_state.update_status(TaskStatus.EXECUTING, f"Executing step 1 of {total_steps}: {plan.steps[0].description}")

        plan_start_time = time.perf_counter()
        results: List[ActionResult] = []

        # Per-plan step output binding context
        step_outputs: Dict[str, Dict[str, Any]] = {}
        last_file_path: Optional[str] = None

        for idx, step in enumerate(plan.steps):
            # 1. Check for User Cancellation
            with self._lock:
                if self._is_cancelled:
                    logger.info(f"Plan execution cancelled before step {idx + 1}")
                    app_state.mark_cancelled("Task execution cancelled by user.")
                    duration_ms = (time.perf_counter() - plan_start_time) * 1000.0
                    event_bus.publish(TaskCancelledEvent(
                        task_id=task_id,
                        reason="Task execution cancelled by user.",
                        duration_ms=duration_ms
                    ))
                    break

            # 2. Build ActionRequest from PlanStep
            step_dict = step.to_dict()
            action_req = ActionRequest.from_plan_step(
                task_id=task_id,
                step_dict=step_dict,
                default_timeout=config.executor.action_timeout_seconds
            )

            # Resolve Dynamic Step Output Binding for Filesystem & Downstream Actions
            if action_req.capability in ("RENAME_FILE", "MOVE_FILE", "READ_FILE"):
                src_val = action_req.parameters.get("source_path") or action_req.target.name
                if (not src_val or src_val in ("selected_file", "latest.pdf", "latest_file", "")) and last_file_path:
                    action_req.parameters["source_path"] = last_file_path
                    action_req.target.name = last_file_path
                elif src_val in ("selected_file", "") and not last_file_path:
                    # Missing prerequisite step result: Fail safely
                    logger.error(f"Step {idx + 1} ({action_req.capability}) failed: Missing prerequisite file output from prior step.")
                    res = ActionResult(
                        action_id=action_req.action_id,
                        task_id=action_req.task_id,
                        capability=action_req.capability,
                    )
                    res.mark_completed(ActionStatus.FAILED, "Missing required output from previous step.", error_code="MISSING_DEPENDENCY_RESULT")
                    results.append(res)
                    self._record_action_completed(res, idx)
                    app_state.mark_failed("Missing required output from previous step.")
                    break
            elif action_req.capability == "VERIFY_STATE":
                target_val = action_req.target.name
                if (not target_val or target_val in ("selected_file", "")) and last_file_path:
                    action_req.target.name = Path(last_file_path).name

            # Update AppState for current step
            app_state.advance_step(idx, f"Step {idx + 1} of {total_steps}: {step.description}")

            # 3. Prevent Duplicate Execution (Action Locking by action_id or step_id)
            with self._lock:
                if action_req.action_id in self._completed_action_ids or action_req.step_id in self._completed_action_ids:
                    logger.warning(f"Skipping duplicate execution of action [{action_req.action_id}] (step: {action_req.step_id})")
                    continue

            # 4. Publish ActionRequestedEvent
            event_bus.publish(ActionRequestedEvent(
                action_id=action_req.action_id,
                task_id=action_req.task_id,
                step_id=action_req.step_id,
                step_index=idx,
                action_type=action_req.capability,
                capability=action_req.capability,
                target=action_req.target.name or "target",
                risk_level=action_req.risk_level.value,
                requires_confirmation=action_req.requires_confirmation,
                parameters=action_req.parameters,
            ))

            # 5. Security & Safety Gate
            allowed, reason, err_code = self.safety_gate.evaluate_action(action_req)
            if not allowed:
                logger.warning(f"Action [{action_req.action_id}] blocked by Safety Gate: {reason}")
                res = ActionResult(
                    action_id=action_req.action_id,
                    task_id=action_req.task_id,
                    capability=action_req.capability,
                )
                res.mark_completed(ActionStatus.BLOCKED, reason, error_code=err_code)
                results.append(res)
                self._record_action_completed(res, idx)
                app_state.mark_failed(f"Action blocked: {reason}")
                break

            # 6. Human-in-the-Loop Confirmation Gate
            if self.safety_gate.requires_user_confirmation(action_req):
                binding = self.safety_gate.create_confirmation_request(action_req, step.description)
                approved = self._await_confirmation(binding)
                if not approved:
                    res = ActionResult(
                        action_id=action_req.action_id,
                        task_id=action_req.task_id,
                        capability=action_req.capability,
                    )
                    res.mark_completed(ActionStatus.CANCELLED, "Action rejected or timed out by user.", error_code="CONFIRMATION_REJECTED")
                    results.append(res)
                    self._record_action_completed(res, idx)
                    app_state.mark_failed("Action confirmation rejected.")
                    break

            # 7. Dispatch to Specialized Capability Executor
            before_state = self._capture_before_state(action_req)
            start_time = time.perf_counter()
            action_res = self._dispatch_capability(action_req)
            action_res.duration_ms = (time.perf_counter() - start_time) * 1000.0

            results.append(action_res)
            self._record_action_completed(action_res, idx)

            # Record step outputs for downstream step binding
            if action_res.success:
                step_outputs[step.step_id] = action_res.evidence
                if action_req.capability == "FIND_FILE":
                    fp = action_res.evidence.get("found_path")
                    if fp:
                        last_file_path = fp
                elif action_req.capability in ("RENAME_FILE", "MOVE_FILE"):
                    dp = action_res.evidence.get("destination_path")
                    if dp:
                        last_file_path = dp

            # 8. Postcondition Verification (Phase 8)
            verif_res: Optional[VerificationResult] = None
            if config.verification.enabled:
                app_state.mark_verifying(f"Verifying step {idx + 1}: {step.description}")
                verif_res = self.verification_engine.verify_action(
                    action_req=action_req,
                    action_res=action_res,
                    before_state=before_state,
                )

            self.step_verifications.append((action_res, verif_res))

            # 9. Failure / Recovery Evaluation (Phase 8)
            action_failed = not action_res.success
            verif_failed = verif_res is not None and not verif_res.verified

            if action_failed or verif_failed:
                logger.warning(
                    f"Step {idx + 1} issue detected: action_success={action_res.success}, "
                    f"verified={verif_res.verified if verif_res else 'N/A'}"
                )

                if config.recovery.enabled:
                    app_state.mark_recovering(f"Evaluating recovery for step {idx + 1}...")
                    decision = self.recovery_manager.evaluate_failure(
                        action_req=action_req,
                        action_res=action_res,
                        verif_res=verif_res,
                    )

                    if decision.decision in (RecoveryDecisionType.RETRY, RecoveryDecisionType.REPERCEIVE):
                        attempt = self.recovery_manager.record_attempt(action_req.action_id)
                        logger.info(f"Executing recovery attempt {attempt} for step {idx + 1} ({decision.decision.value})")

                        retry_allowed, retry_reason, _ = self.safety_gate.evaluate_action(action_req)
                        if retry_allowed:
                            retry_start = time.perf_counter()
                            retry_res = self._dispatch_capability(action_req)
                            retry_res.duration_ms = (time.perf_counter() - retry_start) * 1000.0

                            retry_verif = self.verification_engine.verify_action(
                                action_req=action_req,
                                action_res=retry_res,
                                before_state=before_state,
                            )
                            results[-1] = retry_res
                            self.step_verifications[-1] = (retry_res, retry_verif)

                            if retry_res.success and retry_verif.verified:
                                logger.info(f"Step {idx + 1} recovered successfully!")
                                continue

                    elif decision.decision == RecoveryDecisionType.ASK_USER:
                        app_state.mark_uncertain(f"Uncertain state at step {idx + 1}: {decision.reason}")
                        break

                # If recovery could not resolve
                err_msg = verif_res.mismatch if (verif_res and verif_res.mismatch) else action_res.message
                logger.error(f"Step {idx + 1} halted: {err_msg}")
                break

        # 10. Holistic Task-Level Verification (Phase 8)
        task_res = self.task_verifier.evaluate_task_plan(plan, self.step_verifications)
        self.last_task_verification = task_res

        total_duration_ms = (time.perf_counter() - plan_start_time) * 1000.0

        if task_res.status == "VERIFIED_SUCCESS":
            logger.info(f"Plan [{plan.plan_id}] fully verified: {task_res.message}")
            app_state.mark_completed(task_res.message)
            event_bus.publish(TaskCompletedEvent(
                task_id=task_id,
                status="COMPLETED",
                final_outcome=task_res.message,
                verification_status="VERIFIED",
                duration_ms=total_duration_ms
            ))
        elif task_res.status == "PARTIALLY_COMPLETED":
            logger.warning(f"Plan [{plan.plan_id}] partially completed: {task_res.message}")
            app_state.mark_partially_completed(task_res.message)
            event_bus.publish(TaskCompletedEvent(
                task_id=task_id,
                status="PARTIALLY_COMPLETED",
                final_outcome=task_res.message,
                verification_status="PARTIAL",
                duration_ms=total_duration_ms
            ))
        elif task_res.status == "UNCERTAIN":
            logger.warning(f"Plan [{plan.plan_id}] outcome uncertain: {task_res.message}")
            app_state.mark_uncertain(task_res.message)
            event_bus.publish(TaskCompletedEvent(
                task_id=task_id,
                status="UNCERTAIN",
                final_outcome=task_res.message,
                verification_status="UNCERTAIN",
                duration_ms=total_duration_ms
            ))
        else:
            logger.error(f"Plan [{plan.plan_id}] failed verification: {task_res.message}")
            app_state.mark_failed(task_res.message)
            event_bus.publish(TaskFailedEvent(
                task_id=task_id,
                error_code="VERIFICATION_FAILED",
                error_message=task_res.message,
                duration_ms=total_duration_ms
            ))

        return results

    def _capture_before_state(self, action_req: ActionRequest) -> Optional[Dict[str, Any]]:
        """Captures lightweight pre-action state for comparative verification."""
        cap = action_req.capability
        if cap in ("MOVE_FILE", "RENAME_FILE", "READ_FILE"):
            src = action_req.parameters.get("source") or action_req.parameters.get("path") or action_req.target.name
            if src:
                try:
                    p = Path(src).resolve()
                    if p.exists():
                        stat = p.stat()
                        return {"path": str(p), "exists": True, "size_bytes": stat.st_size, "mtime": stat.st_mtime}
                except Exception:
                    pass
        return None


    def cancel(self) -> None:
        """Signals cancellation of currently executing plan."""
        with self._lock:
            self._is_cancelled = True
        logger.info("ActionExecutor cancellation requested.")

    def _dispatch_capability(self, req: ActionRequest) -> ActionResult:
        """Routes ActionRequest to the proper capability executor."""
        cap = req.capability
        if cap in ("CLICK_UI_ELEMENT", "DOUBLE_CLICK_UI_ELEMENT", "SCROLL", "OBSERVE_SCREEN", "FIND_UI_ELEMENT", "VERIFY_STATE"):
            return self.ui_executor.execute(req)
        elif cap in ("TYPE_TEXT", "PRESS_KEY", "HOTKEY"):
            return self.keyboard_executor.execute(req)
        elif cap in ("SWITCH_WINDOW", "FOCUS_WINDOW", "LAUNCH_APPLICATION"):
            return self.window_executor.execute(req)
        elif cap in ("FIND_FILE", "READ_FILE", "CREATE_FOLDER", "RENAME_FILE", "MOVE_FILE", "DELETE_FILE"):
            return self.file_executor.execute(req)
        else:
            res = ActionResult(action_id=req.action_id, task_id=req.task_id, capability=cap)
            res.mark_completed(ActionStatus.FAILED, f"Unknown executor routing for capability '{cap}'.", error_code="NO_EXECUTOR")
            return res

    def _await_confirmation(self, binding: Any, poll_interval: float = 0.1) -> bool:
        """Polls until user confirmation resolution or timeout."""
        while not self._is_cancelled:
            resolved, approved, _ = self.safety_gate.check_confirmation_status(binding)
            if resolved:
                return approved
            time.sleep(poll_interval)
        return False

    def _record_action_completed(self, res: ActionResult, step_index: int) -> None:
        """Records action in local history, locks action_id, and emits event."""
        with self._lock:
            self._completed_action_ids.add(res.action_id)
            self._execution_history.append(res)

        event_bus.publish(ActionExecutedEvent(
            action_id=res.action_id,
            task_id=res.task_id,
            step_id="",
            step_index=step_index,
            action_type=res.capability,
            capability=res.capability,
            success=res.success,
            status=res.status.value,
            result_details=res.message,
            error_code=res.error_code,
            duration_ms=res.duration_ms,
        ))


# Global action executor singleton
action_executor = ActionExecutor()
