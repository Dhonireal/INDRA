"""
VisionPilot Verification Strategy Registry.

Maintains available verification strategies and dispatches by ExpectedResultType:
- File strategies: FileExistsVerifier, FileAbsentVerifier, FileRenamedVerifier, FileMovedVerifier
- UI strategies: UIElementPresentVerifier, UIElementAbsentVerifier, TextPresentVerifier, TextAbsentVerifier, WindowActiveVerifier, ValueChangedVerifier
- Supports custom verification provider registration.
"""
from typing import Dict, List, Optional, Type

from app.core.logger import logger
from app.execution.path_policy import PathSecurityPolicy
from app.perception.perception_engine import PerceptionEngine
from app.verification.schema import ExpectedResultType
from app.verification.strategies.base import VerificationStrategy
from app.verification.strategies.file_strategies import (
    FileAbsentVerifier, FileExistsVerifier, FileMovedVerifier, FileRenamedVerifier
)
from app.verification.strategies.ui_strategies import (
    StructuredStateVerifier, TextAbsentVerifier, TextPresentVerifier,
    UIElementAbsentVerifier, UIElementPresentVerifier, ValueChangedVerifier,
    WindowActiveVerifier
)


class VerificationStrategyRegistry:
    """Registry managing available verification strategies."""

    def __init__(
        self,
        path_policy: Optional[PathSecurityPolicy] = None,
        perception_engine: Optional[PerceptionEngine] = None,
    ) -> None:
        self.path_policy = path_policy or PathSecurityPolicy()
        self.perception_engine = perception_engine

        self._strategies: List[VerificationStrategy] = []
        self._register_default_strategies()

    def _register_default_strategies(self) -> None:
        """Initializes built-in verification strategies."""
        # Filesystem
        self.register(FileExistsVerifier(self.path_policy))
        self.register(FileAbsentVerifier(self.path_policy))
        self.register(FileRenamedVerifier(self.path_policy))
        self.register(FileMovedVerifier(self.path_policy))

        # UI & Windows
        self.register(UIElementPresentVerifier(self.perception_engine))
        self.register(UIElementAbsentVerifier(self.perception_engine))
        self.register(TextPresentVerifier(self.perception_engine))
        self.register(TextAbsentVerifier(self.perception_engine))
        self.register(WindowActiveVerifier(self.perception_engine))
        self.register(ValueChangedVerifier())
        self.register(StructuredStateVerifier())

    def register(self, strategy: VerificationStrategy, prepend: bool = True) -> None:
        """Registers a verification strategy. Defaults to prepending so custom verifiers override built-ins."""
        if strategy not in self._strategies:
            if prepend:
                self._strategies.insert(0, strategy)
            else:
                self._strategies.append(strategy)
            logger.debug(f"Registered verification strategy: {strategy.strategy_name}")

    def get_strategy(self, expected_type: ExpectedResultType) -> Optional[VerificationStrategy]:
        """Finds the first strategy capable of verifying the given ExpectedResultType."""
        for strat in self._strategies:
            if strat.can_verify(expected_type):
                return strat
        return None

    def list_strategies(self) -> List[str]:
        """Returns names of all registered strategies."""
        return [s.strategy_name for s in self._strategies]


# Global default registry
strategy_registry = VerificationStrategyRegistry()
