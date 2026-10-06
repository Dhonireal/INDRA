"""
VisionPilot Verification Strategy Base Interface.

Defines the contract for all modular verification strategies:
- Evaluates ActionResult against ExpectedResult
- Inspects system / desktop state (UIA, OCR, Filesystem)
- Performs deterministic comparison
- Returns strongly typed VerificationResult
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.execution.schema import ActionResult
from app.verification.schema import ExpectedResult, ExpectedResultType, VerificationResult


class VerificationStrategy(ABC):
    """Abstract base class for all verification strategies."""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Unique identifier for this strategy."""
        pass

    @abstractmethod
    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        """Returns True if this strategy handles the given ExpectedResultType."""
        pass

    @abstractmethod
    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Executes verification inspection and comparison.
        Returns a VerificationResult with evidence and status.
        """
        pass
