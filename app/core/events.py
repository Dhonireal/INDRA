"""
VisionPilot Event Bus and Event Schemas.

Enables asynchronous and decoupled communication between the UI, Agent,
Perception, Safety, Action, and Verification subsystems.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type


@dataclass
class Event:
    """Base class for all VisionPilot events."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CommandSubmittedEvent(Event):
    raw_text: str = ""
    source: str = "text"


@dataclass
class CommandReceivedEvent(Event):
    command_id: str = ""
    raw_text: str = ""
    source: str = "text"


@dataclass
class CommandValidatedEvent(Event):
    command_id: str = ""
    raw_text: str = ""
    length: int = 0


@dataclass
class CommandNormalizedEvent(Event):
    command_id: str = ""
    raw_text: str = ""
    normalized_text: str = ""


@dataclass
class CommandRejectedEvent(Event):
    command_id: str = ""
    raw_text: str = ""
    reason: str = ""
    error_code: str = "VALIDATION_ERROR"


@dataclass
class CommandReadyEvent(Event):
    command_id: str = ""
    task_id: str = ""
    prompt: str = ""


@dataclass
class CommandCancelledEvent(Event):
    command_id: str = ""
    reason: str = "User requested cancellation"


@dataclass
class TaskCreatedEvent(Event):
    task_id: str = ""
    command: str = ""
    source: str = "text"  # "text" or "voice"


@dataclass
class TaskStatusChangedEvent(Event):
    task_id: str = ""
    old_status: str = ""
    new_status: str = ""
    message: str = ""


@dataclass
class TaskCompletedEvent(Event):
    task_id: str = ""
    status: str = "COMPLETED"  # COMPLETED, PARTIALLY_COMPLETED, UNCERTAIN
    final_outcome: str = ""
    verification_status: str = "VERIFIED"
    duration_ms: float = 0.0


@dataclass
class TaskFailedEvent(Event):
    task_id: str = ""
    error_code: str = ""
    error_message: str = ""
    duration_ms: float = 0.0


@dataclass
class TaskCancelledEvent(Event):
    task_id: str = ""
    reason: str = "User requested cancellation"
    duration_ms: float = 0.0


@dataclass
class TaskInterruptedEvent(Event):
    task_id: str = ""
    reason: str = "Session interrupted by shutdown or crash"


@dataclass
class PlanGeneratedEvent(Event):
    task_id: str = ""
    command_id: str = ""
    plan_id: str = ""
    goal: str = ""
    summary: str = ""
    risk_level: str = "SAFE"
    requires_confirmation: bool = False
    step_count: int = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    runtime: str = ""


@dataclass
class PlanClarificationRequiredEvent(Event):
    task_id: str = ""
    command_id: str = ""
    question: str = ""
    candidates: List[str] = field(default_factory=list)
    ambiguity_reason: str = ""


@dataclass
class PlanRejectedEvent(Event):
    task_id: str = ""
    command_id: str = ""
    reason: str = ""
    error_code: str = "PLAN_REJECTED"


@dataclass
class PlanningCancelledEvent(Event):
    task_id: str = ""
    command_id: str = ""
    reason: str = "User requested cancellation"


@dataclass
class ActionRequestedEvent(Event):
    action_id: str = ""
    task_id: str = ""
    step_id: str = ""
    step_index: int = 0
    action_type: str = ""
    capability: str = ""
    target: str = ""
    risk_level: str = "LOW"
    requires_confirmation: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionExecutedEvent(Event):
    action_id: str = ""
    task_id: str = ""
    step_id: str = ""
    step_index: int = 0
    action_type: str = ""
    capability: str = ""
    success: bool = True
    status: str = "SUCCESS"  # SUCCESS, FAILED, TIMEOUT, BLOCKED, UNKNOWN_RESULT
    result_details: str = ""
    error_code: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class ActionBlockedEvent(Event):
    action_id: str = ""
    task_id: str = ""
    step_id: str = ""
    capability: str = ""
    reason: str = ""
    error_code: str = "ACTION_BLOCKED"


@dataclass
class SafetyConfirmationRequiredEvent(Event):
    confirmation_id: str = ""
    task_id: str = ""
    action_id: str = ""
    step_id: str = ""
    step_index: int = 0
    action_type: str = ""
    capability: str = ""
    target: str = ""
    risk_level: str = "HIGH"
    description: str = ""
    expires_at: Optional[datetime] = None


@dataclass
class SafetyConfirmationResolvedEvent(Event):
    confirmation_id: str = ""
    task_id: str = ""
    action_id: str = ""
    step_id: str = ""
    step_index: int = 0
    approved: bool = False
    reason: str = ""


@dataclass
class ConfirmationExpiredEvent(Event):
    confirmation_id: str = ""
    task_id: str = ""
    action_id: str = ""
    reason: str = "User confirmation expired"


@dataclass
class VerificationStartedEvent(Event):
    verification_id: str = ""
    task_id: str = ""
    action_id: str = ""
    step_id: str = ""
    strategy: str = ""
    expected_type: str = ""
    target: str = ""


@dataclass
class VerificationCompletedEvent(Event):
    verification_id: str = ""
    task_id: str = ""
    action_id: str = ""
    step_id: str = ""
    status: str = "VERIFIED"  # VERIFIED, FAILED, UNCERTAIN, TIMEOUT
    verified: bool = True
    confidence: float = 1.0
    strategy: str = ""
    expected: str = ""
    observed: str = ""
    mismatch: Optional[str] = None
    duration_ms: float = 0.0
    recovery_recommended: bool = False
    details: str = ""


@dataclass
class RecoveryDecisionEvent(Event):
    decision_id: str = ""
    task_id: str = ""
    action_id: str = ""
    decision: str = ""  # RETRY, REPERCEIVE, REPLAN, ASK_USER, ABORT, MARK_FAILED, MARK_UNCERTAIN
    reason: str = ""
    attempt: int = 1
    max_attempts: int = 3
    risk_level: str = "LOW"


@dataclass
class RecoveryAttemptedEvent(Event):
    task_id: str = ""
    action_id: str = ""
    attempt_number: int = 1
    strategy: str = ""
    outcome: str = ""


@dataclass
class ScreenCapturedEvent(Event):
    capture_id: str = ""
    width: int = 0
    height: int = 0
    scope: str = "active_window"


@dataclass
class PerceptionCompletedEvent(Event):
    snapshot_id: str = ""
    element_count: int = 0
    ocr_region_count: int = 0
    active_window_title: str = ""
    duration_ms: float = 0.0
    sources: List[str] = field(default_factory=list)


@dataclass
class DeviceStatusChangedEvent(Event):
    cpu: str = ""
    gpu: str = ""
    npu: str = ""
    active_runtime: str = ""
    is_accelerated: bool = False


@dataclass
class ErrorEvent(Event):
    task_id: str = ""
    user_message: str = ""
    technical_details: str = ""
    recoverable: bool = False


EventHandler = Callable[[Any], None]


class EventBus:
    """Thread-safe publish/subscribe event bus."""

    def __init__(self) -> None:
        self._subscribers: Dict[Type[Event], List[EventHandler]] = {}

    def subscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribed handlers."""
        event_type = type(event)
        handlers = self._subscribers.get(event_type, []).copy()
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Isolate handler errors so other subscribers are not impacted
                import traceback
                print(f"[EventBus Error] Exception in handler {handler}: {e}\n{traceback.format_exc()}")

    def clear(self) -> None:
        """Clear all subscriptions (useful in test teardown)."""
        self._subscribers.clear()


# Global EventBus singleton
event_bus = EventBus()
