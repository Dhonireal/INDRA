"""
VisionPilot Action Execution Safety Gate & Confirmation Manager.

Acts as the authoritative security checkpoint between planned action requests
and the capability executors:
- Schema validation
- Capability authorization & risk assessment
- Code injection / shell syntax rejection
- Sensitive credential / password detection
- Action-specific confirmation binding and expiration (Rule 21)
- User cancellation and timeout coordination
"""
from datetime import datetime, timedelta, timezone
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from app.agent.capabilities import CapabilityRegistry, capability_registry
from app.agent.task_schema import RiskLevel
from app.core.config import config
from app.core.events import (
    event_bus, ActionBlockedEvent, ConfirmationExpiredEvent,
    SafetyConfirmationRequiredEvent, SafetyConfirmationResolvedEvent
)
from app.core.exceptions import SafetyViolationError
from app.core.logger import logger
from app.core.state import app_state, TaskStatus
from app.execution.schema import ActionRequest, ConfirmationBinding


class ActionSafetyGate:
    """Security and confirmation gate for all computer actions."""

    # Prohibited shell syntax and script commands
    _FORBIDDEN_EXEC_PATTERNS = [
        re.compile(r"\b(powershell|pwsh|cmd\.exe)\b", re.IGNORECASE),
        re.compile(r"\b(subprocess|os\.system|eval\(|exec\(|__import__)\b", re.IGNORECASE),
        re.compile(r"\b(rmdir\s+/s|format\s+[a-z]:|diskpart|regedit)\b", re.IGNORECASE),
        re.compile(r"<\s*script\b", re.IGNORECASE),
    ]

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or capability_registry
        self._lock = threading.Lock()
        self._pending_confirmations: Dict[str, ConfirmationBinding] = {}
        self._resolved_confirmations: Dict[str, ConfirmationBinding] = {}
        
        # Subscribe to UI confirmation resolution
        event_bus.subscribe(SafetyConfirmationResolvedEvent, self._handle_confirmation_resolved)

    def evaluate_action(self, request: ActionRequest) -> Tuple[bool, str, Optional[str]]:
        """
        Evaluates action against safety policy.
        Returns: (is_allowed: bool, reason: str, error_code: Optional[str])
        """
        cap_name = request.capability
        # 1. Permanent Deletion & Blocked Defense
        if cap_name in ("DELETE_FILE", "DELETE_FOLDER"):
            return False, "Permanent deletion is strictly prohibited in Phase 7.", "DELETION_BLOCKED"

        if not self.registry.is_known(cap_name):
            return False, f"Capability '{cap_name}' is not registered.", "UNKNOWN_CAPABILITY"

        cap_def = self.registry.get(cap_name)
        if cap_def and cap_def.default_risk == RiskLevel.BLOCKED:
            return False, f"Action '{cap_name}' is permanently BLOCKED by safety policy.", "OPERATION_BLOCKED"

        if not cap_def or not cap_def.available or not cap_def.enabled:
            return False, f"Capability '{cap_name}' is not enabled or available for execution.", "CAPABILITY_UNAVAILABLE"

        # 2. Check for Arbitrary Code / Shell Injection
        for param_k, param_v in request.parameters.items():
            if isinstance(param_v, str):
                for pattern in self._FORBIDDEN_EXEC_PATTERNS:
                    if pattern.search(param_v):
                        return False, f"Action parameter '{param_k}' contains forbidden executable code: {param_v[:30]}.", "CODE_INJECTION_BLOCKED"

        # 3. Permanent Deletion Defense
        if cap_name in ("DELETE_FILE", "DELETE_FOLDER"):
            return False, "Permanent deletion is strictly prohibited in Phase 7.", "DELETION_BLOCKED"

        return True, "Action cleared safety gate.", None

    def requires_user_confirmation(self, request: ActionRequest) -> bool:
        """Determines if the action requires explicit human-in-the-loop approval."""
        if request.requires_confirmation:
            return True

        cap_def = self.registry.get(request.capability)
        if cap_def and cap_def.requires_confirmation:
            return True

        # Policy checks based on risk levels
        if request.risk_level in (RiskLevel.HIGH, RiskLevel.BLOCKED):
            return True
        if request.risk_level == RiskLevel.MEDIUM and config.safety.confirm_medium_risk:
            return True
        if request.risk_level == RiskLevel.LOW and not config.safety.auto_approve_low_risk:
            return True

        return False

    def create_confirmation_request(self, request: ActionRequest, description: str = "") -> ConfirmationBinding:
        """Creates an action-specific confirmation binding and dispatches UI event."""
        timeout_sec = config.executor.confirmation_timeout_seconds
        expires = datetime.now(timezone.utc) + timedelta(seconds=timeout_sec)

        binding = ConfirmationBinding(
            task_id=request.task_id,
            action_id=request.action_id,
            capability=request.capability,
            target_summary=request.target.name or "Target",
            parameters_summary=str(request.parameters),
            risk_level=request.risk_level,
            description=description or f"Confirm {request.capability} on {request.target.name or 'target'}",
            expires_at=expires,
        )

        with self._lock:
            self._pending_confirmations[binding.confirmation_id] = binding

        # Update application state
        app_state.set_confirmation_request({
            "confirmation_id": binding.confirmation_id,
            "action_id": request.action_id,
            "action_type": request.capability,
            "target": request.target.name or "Target",
            "risk_level": request.risk_level.value,
            "description": binding.description,
        })

        # Emit safety confirmation required event
        event_bus.publish(SafetyConfirmationRequiredEvent(
            confirmation_id=binding.confirmation_id,
            task_id=request.task_id,
            action_id=request.action_id,
            step_id=request.step_id,
            step_index=request.step_order - 1,
            action_type=request.capability,
            capability=request.capability,
            target=request.target.name or "Target",
            risk_level=request.risk_level.value,
            description=binding.description,
            expires_at=expires,
        ))

        logger.info(f"Confirmation requested for action [{request.action_id}] (expires in {timeout_sec}s)")
        return binding

    def check_confirmation_status(self, binding: ConfirmationBinding) -> Tuple[bool, bool, str]:
        """
        Checks resolution status of a confirmation binding.
        Returns: (is_resolved: bool, is_approved: bool, reason: str)
        """
        with self._lock:
            # Check expiration
            if binding.is_expired():
                if binding.confirmation_id in self._pending_confirmations:
                    del self._pending_confirmations[binding.confirmation_id]
                event_bus.publish(ConfirmationExpiredEvent(
                    confirmation_id=binding.confirmation_id,
                    task_id=binding.task_id,
                    action_id=binding.action_id,
                ))
                return True, False, "Confirmation request timed out."

            resolved = self._resolved_confirmations.get(binding.confirmation_id)
            if resolved:
                return True, resolved.is_approved, "User approved" if resolved.is_approved else "User rejected"

            return False, False, "Waiting for user response"

    def _handle_confirmation_resolved(self, ev: SafetyConfirmationResolvedEvent) -> None:
        """Handles user approval or rejection from UI dialog."""
        with self._lock:
            conf_id = ev.confirmation_id
            binding = self._pending_confirmations.pop(conf_id, None)
            if not binding:
                # Find by action_id fallback
                for cid, b in list(self._pending_confirmations.items()):
                    if b.action_id == ev.action_id:
                        binding = self._pending_confirmations.pop(cid)
                        conf_id = cid
                        break

            if binding:
                binding.is_resolved = True
                binding.is_approved = ev.approved
                self._resolved_confirmations[conf_id] = binding
                logger.info(f"Confirmation [{conf_id}] resolved: {'APPROVED' if ev.approved else 'REJECTED'}")

        app_state.clear_confirmation_request()


# Global safety gate singleton
action_safety_gate = ActionSafetyGate()
