"""
VisionPilot Application State Management.

Centralizes observable state across agent execution, UI state, and hardware status
with thread-safe mutation and notification hooks.
"""
from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Any, Callable, Dict, List, Optional


class TaskStatus(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    ANALYZING = "ANALYZING"
    PLANNING = "PLANNING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    UNCERTAIN = "UNCERTAIN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


@dataclass
class HardwareState:
    cpu_name: str = "Unknown CPU"
    gpu_name: str = "Unknown GPU"
    npu_name: str = "Unknown NPU"
    npu_present: bool = False
    active_runtime: str = "CPU"
    is_accelerated: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AppState:
    """Thread-safe application state container."""
    status: TaskStatus = TaskStatus.IDLE
    status_message: str = "Ready"
    current_task_id: Optional[str] = None
    current_command: Optional[str] = None
    current_plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step_index: int = -1
    pending_confirmation: Optional[Dict[str, Any]] = None
    hardware: HardwareState = field(default_factory=HardwareState)
    last_error: Optional[str] = None
    
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _listeners: List[Callable[["AppState"], None]] = field(default_factory=list, init=False, repr=False)

    def subscribe(self, listener: Callable[["AppState"], None]) -> None:
        """Register a callback for state changes."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[["AppState"], None]) -> None:
        """Unregister a callback."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify(self) -> None:
        """Notify listeners of state mutation."""
        listeners_copy = self._listeners.copy()
        for listener in listeners_copy:
            try:
                listener(self)
            except Exception as e:
                print(f"[State Notify Error] Listener failed: {e}")

    def update_status(self, status: TaskStatus, message: str = "") -> None:
        """Update task status with notification."""
        with self._lock:
            self.status = status
            if message:
                self.status_message = message
        self._notify()

    def set_task(self, task_id: str, command: str) -> None:
        """Initialize active task."""
        with self._lock:
            self.current_task_id = task_id
            self.current_command = command
            self.current_plan = []
            self.current_step_index = -1
            self.pending_confirmation = None
            self.last_error = None
            self.status = TaskStatus.ANALYZING
            self.status_message = f"Processing command: {command}"
        self._notify()

    def set_plan(self, plan: List[Dict[str, Any]]) -> None:
        """Set structured plan steps."""
        with self._lock:
            self.current_plan = plan
            self.current_step_index = 0
            self.status = TaskStatus.EXECUTING
            self.status_message = f"Executing plan ({len(plan)} steps)"
        self._notify()

    def advance_step(self, step_index: int, status_message: str = "") -> None:
        """Advance to next execution step."""
        with self._lock:
            self.current_step_index = step_index
            if status_message:
                self.status_message = status_message
        self._notify()

    def set_confirmation_request(self, request: Dict[str, Any]) -> None:
        """Set pending user confirmation request."""
        with self._lock:
            self.pending_confirmation = request
            self.status = TaskStatus.WAITING_CONFIRMATION
            self.status_message = f"Confirmation required for: {request.get('action_type', 'Action')}"
        self._notify()

    def clear_confirmation_request(self) -> None:
        """Clear pending confirmation request."""
        with self._lock:
            self.pending_confirmation = None
        self._notify()

    def set_hardware(self, hardware: HardwareState) -> None:
        """Set detected hardware telemetry."""
        with self._lock:
            self.hardware = hardware
        self._notify()

    def mark_completed(self, message: str = "Task completed successfully.") -> None:
        """Mark task as successfully completed."""
        with self._lock:
            self.status = TaskStatus.COMPLETED
            self.status_message = message
            self.pending_confirmation = None
        self._notify()

    def mark_verifying(self, message: str = "Verifying action result...") -> None:
        """Mark task as currently verifying postconditions."""
        with self._lock:
            self.status = TaskStatus.VERIFYING
            self.status_message = message
        self._notify()

    def mark_recovering(self, message: str = "Attempting safe recovery...") -> None:
        """Mark task as executing a recovery strategy."""
        with self._lock:
            self.status = TaskStatus.RECOVERING
            self.status_message = message
        self._notify()

    def mark_partially_completed(self, message: str = "Task partially completed.") -> None:
        """Mark task as partially completed when a non-fatal step stops."""
        with self._lock:
            self.status = TaskStatus.PARTIALLY_COMPLETED
            self.status_message = message
            self.pending_confirmation = None
        self._notify()

    def mark_uncertain(self, message: str = "Action result could not be conclusively verified.") -> None:
        """Mark task as uncertain when postcondition cannot be determined."""
        with self._lock:
            self.status = TaskStatus.UNCERTAIN
            self.status_message = message
            self.pending_confirmation = None
        self._notify()

    def mark_failed(self, error_message: str) -> None:
        """Mark task as failed with user message."""
        with self._lock:
            self.status = TaskStatus.FAILED
            self.status_message = error_message
            self.last_error = error_message
            self.pending_confirmation = None
        self._notify()

    def mark_cancelled(self, message: str = "Task was cancelled.") -> None:
        """Mark task as cancelled by user or timeout."""
        with self._lock:
            self.status = TaskStatus.CANCELLED
            self.status_message = message
            self.pending_confirmation = None
        self._notify()

    def mark_interrupted(self, message: str = "Task was interrupted by previous session crash or shutdown.") -> None:
        """Mark task as interrupted from prior abnormal shutdown."""
        with self._lock:
            self.status = TaskStatus.INTERRUPTED
            self.status_message = message
            self.pending_confirmation = None
        self._notify()

    def reset(self) -> None:
        """Reset task state back to IDLE."""
        with self._lock:
            self.status = TaskStatus.IDLE
            self.status_message = "Ready"
            self.current_task_id = None
            self.current_command = None
            self.current_plan = []
            self.current_step_index = -1
            self.pending_confirmation = None
            self.last_error = None
        self._notify()


# Global application state instance
app_state = AppState()
