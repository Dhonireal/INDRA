"""
VisionPilot Reasoning Provider Interface.

Defines the abstract contract for AI reasoning and planning providers:
- Availability checking
- Plan generation from PlannerContext
- Plan explanation
- Cancellation
- Runtime and accelerator telemetry
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.agent.context_manager import PlannerContext
from app.agent.task_schema import TaskPlan


class ReasoningProvider(ABC):
    """Abstract base class for all VisionPilot planning and reasoning providers."""

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider and required local models/runtimes are ready."""
        pass

    @abstractmethod
    def initialize(self) -> bool:
        """Initializes model weights, runtime sessions, or deterministic engines."""
        pass

    @abstractmethod
    def generate_plan(self, context: PlannerContext, timeout_seconds: float = 10.0) -> TaskPlan:
        """Generates a structured, machine-readable TaskPlan from context."""
        pass

    @abstractmethod
    def explain_plan(self, plan: TaskPlan) -> str:
        """Returns a concise, user-friendly summary of the plan without chain-of-thought."""
        pass

    @abstractmethod
    def cancel(self) -> None:
        """Requests cancellation of ongoing inference or planning."""
        pass

    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """Returns provider metadata (name, model, version, local status)."""
        pass

    @abstractmethod
    def get_runtime_info(self) -> Dict[str, Any]:
        """Returns hardware runtime telemetry (CPU, GPU, NPU, memory)."""
        pass
