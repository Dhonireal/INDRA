"""
VisionPilot Verification Engine.

Orchestrates postcondition verification across UI, Windows, and Filesystem actions:
- Inspects system state against declarative ExpectedResult specifications.
- Implements bounded temporal polling (e.g. 100ms intervals up to timeout).
- Prevents False Success: never assumes action succeeded merely because executor returned.
- Handles UNKNOWN_RESULT / TIMEOUT: verifies if intended side effect actually occurred.
- Maintains strict separation between ActionResult and VerificationResult.
- Publishes VerificationStartedEvent and VerificationCompletedEvent.
- Records structured verification audit history.
"""
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from app.core.config import config
from app.core.events import (
    event_bus, VerificationCompletedEvent, VerificationStartedEvent
)
from app.core.logger import logger
from app.execution.schema import ActionRequest, ActionResult, ActionStatus
from app.perception.models import ScreenState
from app.perception.perception_engine import PerceptionEngine
from app.verification.schema import (
    ExpectedResult, ExpectedResultType, VerificationConfidence,
    VerificationResult, VerificationStatus
)
from app.verification.strategies.registry import (
    VerificationStrategyRegistry, strategy_registry
)


class VerificationEngine:
    """Core engine evaluating postconditions and determining action success."""

    def __init__(
        self,
        registry: Optional[VerificationStrategyRegistry] = None,
        perception_engine: Optional[PerceptionEngine] = None,
    ) -> None:
        self.registry = registry or strategy_registry
        self.perception_engine = perception_engine
        self._history: List[VerificationResult] = []

    def verify_action(
        self,
        action_req: ActionRequest,
        action_res: ActionResult,
        expected: Optional[ExpectedResult] = None,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Evaluates an action's postconditions using bounded temporal polling.
        Returns a strongly typed VerificationResult with evidence.
        """
        start_time = time.perf_counter()

        # 1. Resolve or infer ExpectedResult
        if expected is None:
            expected = ExpectedResult.infer_from_action_request(action_req)

        # 2. Select appropriate verification strategy
        strat = self.registry.get_strategy(expected.type)

        # Publish VerificationStartedEvent
        event_bus.publish(VerificationStartedEvent(
            task_id=action_res.task_id,
            action_id=action_res.action_id,
            step_id=action_req.step_id,
            strategy=strat.strategy_name if strat else "None",
            expected_type=expected.type.value,
            target=expected.target,
        ))

        # If no strategy matches this type, mark NOT_APPLICABLE or UNCERTAIN
        if not strat:
            logger.warning(f"No verification strategy found for ExpectedResultType '{expected.type.value}'")
            res = VerificationResult(
                task_id=action_res.task_id,
                action_id=action_res.action_id,
                strategy="None",
                status=VerificationStatus.NOT_APPLICABLE,
                verified=False,
                confidence=0.0,
                mismatch=f"No verifier registered for {expected.type.value}",
                duration_ms=(time.perf_counter() - start_time) * 1000.0,
            )
            self._record_result(res)
            return res

        # 3. Bounded Temporal Polling Loop
        timeout_s = expected.timeout_seconds or config.verification.default_timeout_seconds
        poll_interval_s = expected.poll_interval_seconds or config.verification.poll_interval_seconds
        deadline = time.perf_counter() + timeout_s

        last_result: Optional[VerificationResult] = None
        attempts = 0

        while True:
            attempts += 1
            # Build execution context for this poll attempt
            eval_context = dict(context or {})

            # If perception engine is available and this is a UI strategy, refresh screen state if needed
            if self.perception_engine and "screen_state" not in eval_context and expected.type in (
                ExpectedResultType.UI_STATE, ExpectedResultType.ELEMENT_PRESENT,
                ExpectedResultType.ELEMENT_ABSENT, ExpectedResultType.TEXT_PRESENT,
                ExpectedResultType.TEXT_ABSENT, ExpectedResultType.WINDOW_ACTIVE
            ):
                try:
                    eval_context["screen_state"] = self.perception_engine.perceive()
                except Exception as e:
                    logger.warning(f"Verification screen perception failed: {e}")

            # Run verifier
            current_result = strat.verify(
                action_result=action_res,
                expected=expected,
                before_state=before_state,
                context=eval_context,
            )
            last_result = current_result

            # If verified, exit polling loop immediately
            if current_result.verified:
                break

            # If deadline reached, exit
            if time.perf_counter() >= deadline:
                break

            # Sleep poll interval before next attempt
            time.sleep(poll_interval_s)

        # 4. Finalize result duration and status
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        final_res = last_result or VerificationResult(
            task_id=action_res.task_id,
            action_id=action_res.action_id,
            strategy=strat.strategy_name,
            status=VerificationStatus.FAILED,
            mismatch="Verification loop failed to evaluate.",
        )
        final_res.duration_ms = duration_ms

        # If it failed because deadline was reached, mark TIMEOUT if appropriate
        if not final_res.verified and time.perf_counter() >= deadline:
            final_res.status = VerificationStatus.TIMEOUT
            final_res.mismatch = f"Verification timed out after {timeout_s:.1f}s waiting for expected state."

        # 5. Handle UNKNOWN_RESULT / TIMEOUT from ActionExecutor
        # If executor was uncertain/timeout, but verification passed -> VERIFIED SUCCESS!
        if action_res.status in (ActionStatus.UNKNOWN_RESULT, ActionStatus.TIMEOUT) and final_res.verified:
            logger.info(f"Action [{action_res.action_id}] was UNKNOWN_RESULT/TIMEOUT, but verified successfully by postcondition!")
            final_res.evidence["recovered_from_unknown"] = True

        self._record_result(final_res)

        # Publish VerificationCompletedEvent
        event_bus.publish(VerificationCompletedEvent(
            verification_id=final_res.verification_id,
            task_id=final_res.task_id,
            action_id=final_res.action_id,
            step_id=action_req.step_id,
            status=final_res.status.value,
            verified=final_res.verified,
            confidence=final_res.confidence,
            strategy=final_res.strategy,
            expected=str(final_res.expected_state),
            observed=str(final_res.actual_state),
            mismatch=final_res.mismatch,
            duration_ms=final_res.duration_ms,
            recovery_recommended=final_res.recovery_recommended,
            details=f"Verification completed in {final_res.duration_ms:.1f}ms ({attempts} polls)",
        ))

        return final_res

    def get_history(self) -> List[VerificationResult]:
        """Returns the audit log of all verification results."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clears verification history."""
        self._history.clear()

    def _record_result(self, res: VerificationResult) -> None:
        self._history.append(res)
        logger.info(
            f"Verification [{res.verification_id}] for action [{res.action_id}]: "
            f"status={res.status.value}, verified={res.verified}, confidence={res.confidence:.2f} ({res.strategy})"
        )


# Global verification engine instance
verification_engine = VerificationEngine()
