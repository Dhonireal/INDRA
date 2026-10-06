"""
VisionPilot Verification Strategies.
"""
from app.verification.strategies.base import VerificationStrategy
from app.verification.strategies.file_strategies import (
    FileAbsentVerifier, FileExistsVerifier, FileMovedVerifier, FileRenamedVerifier
)
from app.verification.strategies.registry import VerificationStrategyRegistry, strategy_registry
from app.verification.strategies.ui_strategies import (
    StructuredStateVerifier, TextAbsentVerifier, TextPresentVerifier,
    UIElementAbsentVerifier, UIElementPresentVerifier, ValueChangedVerifier,
    WindowActiveVerifier
)

__all__ = [
    "VerificationStrategy",
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
    "StructuredStateVerifier",
    "VerificationStrategyRegistry",
    "strategy_registry",
]
