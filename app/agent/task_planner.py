"""
VisionPilot AI Task Planner Orchestrator.

Orchestrates the Phase 6 planning pipeline:
CommandRequest + ScreenState + CapabilityRegistry + Context
    ↓
ReasoningProvider.generate_plan()
    ↓
PlanValidator
    ↓
Plan Repair (bounded 1 attempt)
    ↓
Validated TaskPlan
    ↓
AppState & EventBus notification

CRITICAL: The TaskPlanner is strictly a PLANNER, NOT an executor.
Zero mouse movements, clicks, typing, or filesystem modifications occur here.
"""
import threading
import time
from typing import Any, Dict, List, Optional
from app.agent.capabilities import CapabilityRegistry, capability_registry
from app.agent.context_manager import PlannerContext, PlannerContextManager, planner_context_manager
from app.agent.plan_validator import PlanValidator, plan_validator
from app.agent.providers.local_reasoning import LocalReasoningProvider, local_reasoning_provider
from app.agent.providers.mock_reasoning import MockReasoningProvider
from app.agent.providers.reasoning_provider import ReasoningProvider
from app.agent.task_schema import (
    CommandRequest, PlanStatus, PlanStep, RiskLevel, TaskPlan
)
from app.core.config import config
from app.core.events import (
    event_bus, PlanClarificationRequiredEvent, PlanGeneratedEvent,
    PlanRejectedEvent, PlanningCancelledEvent, ErrorEvent
)
from app.core.exceptions import PlanningError
from app.core.logger import logger
from app.core.state import app_state, TaskStatus
from app.perception.models import ScreenState


class TaskPlanner:
    """Orchestrates structured planning, bounded repair, validation, and lifecycle state."""

    def __init__(
        self,
        provider: Optional[ReasoningProvider] = None,
        validator: Optional[PlanValidator] = None,
        context_mgr: Optional[PlannerContextManager] = None,
        registry: Optional[CapabilityRegistry] = None,
    ) -> None:
        self.validator = validator or plan_validator
        self.context_mgr = context_mgr or planner_context_manager
        self.registry = registry or capability_registry
        
        # Configure Provider based on settings
        if provider:
            self.provider = provider
        elif config.planner.provider == "mock":
            self.provider = MockReasoningProvider()
        else:
            self.provider = local_reasoning_provider

        self._lock = threading.Lock()
        self._active_plan: Optional[TaskPlan] = None
        self._is_cancelled = False

    def create_plan(
        self,
        command_request: CommandRequest,
        screen_state: Optional[ScreenState] = None,
        timeout_seconds: Optional[float] = None
    ) -> TaskPlan:
        """
        Main entry point for generating a validated TaskPlan from a user command and perception.
        """
        timeout = timeout_seconds or config.planner.planning_timeout_seconds
        start_time = time.perf_counter()

        with self._lock:
            self._is_cancelled = False
        if hasattr(self.provider, "_cancelled"):
            self.provider._cancelled = False

        # 1. Update State to PLANNING
        logger.info(f"TaskPlanner generating plan for command [{command_request.command_id}]")
        app_state.update_status(TaskStatus.PLANNING, f"Formulating plan for: {command_request.raw_text}")

        # 2. Build security-bounded PlannerContext
        context = self.context_mgr.build_context(command_request, screen_state)

        # 3. Model / Provider Inference
        try:
            raw_plan = self.provider.generate_plan(context, timeout_seconds=timeout)
        except Exception as e:
            logger.error(f"ReasoningProvider raised exception: {e}", exc_info=True)
            return self._handle_planning_failure(
                command_request.command_id,
                f"Planning engine encountered an error: {str(e)}",
                error_code="INFERENCE_FAILED"
            )

        # Check cancellation
        with self._lock:
            if self._is_cancelled or raw_plan.status == PlanStatus.CANCELLED:
                logger.info(f"Planning was cancelled for command [{command_request.command_id}]")
                raw_plan.status = PlanStatus.CANCELLED
                event_bus.publish(PlanningCancelledEvent(
                    command_id=command_request.command_id,
                    task_id=app_state.current_task_id or "",
                ))
                return raw_plan

        # Check for Clarification Request
        if raw_plan.requires_clarification:
            logger.info(f"Plan requires clarification: '{raw_plan.clarification_question}'")
            raw_plan.status = PlanStatus.NEEDS_CLARIFICATION
            app_state.update_status(TaskStatus.WAITING_CONFIRMATION, raw_plan.clarification_question)
            event_bus.publish(PlanClarificationRequiredEvent(
                command_id=command_request.command_id,
                task_id=app_state.current_task_id or "",
                question=raw_plan.clarification_question,
                candidates=raw_plan.clarification_candidates,
                ambiguity_reason=raw_plan.summary,
            ))
            return raw_plan

        # Check for Unsupported Request
        if raw_plan.status == PlanStatus.UNSUPPORTED:
            logger.warning(f"Plan requested unsupported or blocked operation for command [{command_request.command_id}]")
            app_state.update_status(TaskStatus.FAILED, raw_plan.summary)
            event_bus.publish(PlanRejectedEvent(
                command_id=command_request.command_id,
                task_id=app_state.current_task_id or "",
                reason=raw_plan.summary,
                error_code="UNSUPPORTED_CAPABILITY"
            ))
            return raw_plan

        # 4. Plan Validation
        is_valid, validation_errors = self.validator.validate_plan(raw_plan)
        if not is_valid:
            logger.warning(f"Initial plan invalid, attempting bounded repair: {validation_errors}")
            repaired_plan = self._attempt_repair(context, raw_plan, validation_errors)
            is_valid, validation_errors = self.validator.validate_plan(repaired_plan)
            if not is_valid:
                return self._handle_planning_failure(
                    command_request.command_id,
                    f"Plan schema or safety validation failed: {'; '.join(validation_errors)}",
                    error_code="VALIDATION_FAILED"
                )
            raw_plan = repaired_plan

        # 5. Success: Plan is Validated and Ready
        raw_plan.status = PlanStatus.READY
        raw_plan.task_id = app_state.current_task_id or f"task_{command_request.command_id}"
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"TaskPlan [{raw_plan.plan_id}] ready with {len(raw_plan.steps)} steps in {elapsed_ms:.1f}ms")

        # Update AppState plan (DO NOT execute steps)
        plan_dicts = [step.to_dict() for step in raw_plan.steps]
        # Keep AppState in PLANNING or READY_PREVIEW state (Phase 6 strictly previews, no execution)
        with app_state._lock:
            app_state.current_plan = plan_dicts
            app_state.current_step_index = 0
            app_state.status_message = f"Plan Ready ({len(raw_plan.steps)} steps): {raw_plan.summary}"
        app_state._notify()

        # Publish EventBus PlanGeneratedEvent
        event_bus.publish(PlanGeneratedEvent(
            task_id=raw_plan.task_id,
            command_id=raw_plan.command_id,
            plan_id=raw_plan.plan_id,
            goal=raw_plan.goal,
            summary=raw_plan.summary,
            risk_level=raw_plan.risk_level.value,
            requires_confirmation=raw_plan.requires_confirmation,
            step_count=len(raw_plan.steps),
            steps=plan_dicts,
            provider=raw_plan.planner_provider,
            model=raw_plan.planner_model,
            runtime=raw_plan.planner_runtime,
        ))

        with self._lock:
            self._active_plan = raw_plan
        return raw_plan

    def cancel(self) -> None:
        """Signals cancellation to the planner and underlying provider."""
        with self._lock:
            self._is_cancelled = True
        self.provider.cancel()
        logger.info("TaskPlanner cancellation requested.")

    def _attempt_repair(
        self,
        context: PlannerContext,
        broken_plan: TaskPlan,
        errors: List[str]
    ) -> TaskPlan:
        """Performs one bounded structural repair on order or missing IDs."""
        logger.info("Performing deterministic bounded plan repair...")
        # Repair step numbering and dependencies if corrupted
        repaired_steps: List[PlanStep] = []
        seen_ids = set()

        for idx, step in enumerate(broken_plan.steps):
            step.order = idx + 1
            if not step.step_id or step.step_id in seen_ids:
                step.step_id = f"step_repair_{idx + 1}"
            seen_ids.add(step.step_id)
            # Prune invalid dependencies
            step.depends_on = [dep for dep in step.depends_on if dep in seen_ids and dep != step.step_id]
            repaired_steps.append(step)

        broken_plan.steps = repaired_steps
        return broken_plan

    def _handle_planning_failure(self, command_id: str, message: str, error_code: str) -> TaskPlan:
        """Handles planning errors safely without crashing the application."""
        app_state.update_status(TaskStatus.FAILED, message)
        event_bus.publish(PlanRejectedEvent(
            command_id=command_id,
            task_id=app_state.current_task_id or "",
            reason=message,
            error_code=error_code,
        ))
        event_bus.publish(ErrorEvent(
            task_id=app_state.current_task_id or "",
            user_message="Could not generate a valid plan for this command.",
            technical_details=message,
            recoverable=False,
        ))
        return TaskPlan(
            command_id=command_id,
            goal="",
            summary=message,
            status=PlanStatus.FAILED,
            planner_provider=self.provider.get_provider_info().get("provider_name", "unknown"),
        )


# Global task planner singleton
task_planner = TaskPlanner()
