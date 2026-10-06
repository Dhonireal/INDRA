"""
VisionPilot Mock Reasoning Provider.

Provides deterministic, predefined, and customizable plans for unit tests.
Strictly prohibited from silent production use.
"""
from typing import Any, Dict, List, Optional
from app.agent.context_manager import PlannerContext
from app.agent.providers.reasoning_provider import ReasoningProvider
from app.agent.task_schema import (
    ActionIntent, ActionTarget, PlanStatus, PlanStep, RiskLevel, TaskPlan
)


class MockReasoningProvider(ReasoningProvider):
    """Deterministic mock reasoning provider strictly for testing."""

    def __init__(self, canned_plan: Optional[TaskPlan] = None) -> None:
        self.canned_plan = canned_plan
        self._cancelled = False
        self._initialized = False

    def is_available(self) -> bool:
        return True

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def generate_plan(self, context: PlannerContext, timeout_seconds: float = 10.0) -> TaskPlan:
        if self._cancelled:
            return TaskPlan(
                command_id=context.command_id,
                goal=context.user_command,
                summary="Planning cancelled by user.",
                status=PlanStatus.CANCELLED,
                planner_provider="mock",
            )

        if self.canned_plan:
            plan = self.canned_plan
            plan.command_id = context.command_id
            return plan

        # Default predictable mock plan
        step1 = PlanStep(
            step_id="step_mock_1",
            order=1,
            intent=ActionIntent(
                capability="OBSERVE_SCREEN",
                target=ActionTarget(target_type="WINDOW", name="ActiveWindow"),
            ),
            description="Inspect active window for context",
            expected_result="Active window state captured",
            verification_requirement="CHECK_WINDOW_ACTIVE",
            risk_level=RiskLevel.SAFE,
            reversible=True,
        )
        return TaskPlan(
            command_id=context.command_id,
            goal=f"Mock plan for: {context.user_command}",
            summary="Deterministic mock test plan",
            steps=[step1],
            risk_level=RiskLevel.SAFE,
            status=PlanStatus.READY,
            planner_provider="mock",
            planner_model="MockPlanner-v1",
            planner_runtime="Mock",
            accelerator="Mock",
        )

    def explain_plan(self, plan: TaskPlan) -> str:
        return f"Mock Explanation: Goal: {plan.goal} with {len(plan.steps)} steps."

    def cancel(self) -> None:
        self._cancelled = True

    def get_provider_info(self) -> Dict[str, Any]:
        return {
            "provider_name": "MockReasoningProvider",
            "model_name": "MockPlanner-v1",
            "is_local": True,
            "version": "1.0.0-test",
        }

    def get_runtime_info(self) -> Dict[str, Any]:
        return {
            "runtime": "MockTestRuntime",
            "accelerator": "None",
            "memory_usage_mb": 0.0,
        }
