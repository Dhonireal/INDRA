"""
VisionPilot Verification & Recovery Package.

Exports:
- VerificationEngine & verification_engine singleton
- RecoveryManager & recovery_manager singleton
- TaskVerifier & task_verifier singleton
- VerificationStrategyRegistry & strategy_registry
- All schemas: ExpectedResult, ExpectedResultType, VerificationResult,
  VerificationStatus, VerificationConfidence, RecoveryDecision,
  RecoveryDecisionType, TaskVerificationResult
"""
from app.verification.engine import VerificationEngine, verification_engine
from app.verification.recovery import RecoveryManager, recovery_manager
from app.verification.schema import (
    ExpectedResult, ExpectedResultType, RecoveryDecision,
    RecoveryDecisionType, TaskVerificationResult, VerificationConfidence,
    VerificationResult, VerificationStatus
)
from app.verification.strategies import (
    FileAbsentVerifier, FileExistsVerifier, FileMovedVerifier,
    FileRenamedVerifier, TextAbsentVerifier, TextPresentVerifier,
    UIElementAbsentVerifier, UIElementPresentVerifier, ValueChangedVerifier,
    VerificationStrategy, VerificationStrategyRegistry, WindowActiveVerifier,
    strategy_registry
)
from app.verification.task_verifier import TaskVerifier, task_verifier

__all__ = [
    "VerificationEngine",
    "verification_engine",
    "RecoveryManager",
    "recovery_manager",
    "TaskVerifier",
    "task_verifier",
    "VerificationStrategyRegistry",
    "strategy_registry",
    "VerificationStrategy",
    "ExpectedResult",
    "ExpectedResultType",
    "VerificationResult",
    "VerificationStatus",
    "VerificationConfidence",
    "RecoveryDecision",
    "RecoveryDecisionType",
    "TaskVerificationResult",
    "FileExistsVerifier",
    "FileAbsentVerifier",
    "FileRenamedVerifier",
    "FileMovedVerifier",
    "UIElementPresentVerifier",
    "UIElementAbsentVerifier",
    "TextPresentVerifier",
    "TextAbsentVerifier",
    "WindowActiveVerifier",
    "ValueChangedVerifier",
]
