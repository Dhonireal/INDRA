"""
VisionPilot Command Parser, Validator, and Normalizer.

Transforms raw user text into validated, normalized domain representations without
calling AI models, altering semantic meaning, or evaluating code.
Treats user input strictly as DATA.
"""
import re
import unicodedata
from typing import Tuple
from app.core.config import config
from app.core.exceptions import InvalidCommandError, CommandTooLongError
from app.core.state import app_state
from app.agent.task_schema import CommandContext, CommandSource


class CommandValidator:
    """Validates user command constraints."""

    def __init__(self, max_length: int = 2000, min_length: int = 1) -> None:
        self.max_length = max_length
        self.min_length = min_length

    def validate(self, text: str) -> None:
        """Validates raw command text. Raises domain exceptions on violation."""
        if not isinstance(text, str):
            raise InvalidCommandError("Command must be a text string.", "Invalid command format.")

        # Check empty or whitespace-only
        stripped = text.strip()
        if len(stripped) < self.min_length:
            raise InvalidCommandError(
                "Command is empty or contains only whitespace.",
                "Please enter a command to proceed."
            )

        # Check maximum length
        if len(text) > self.max_length:
            raise CommandTooLongError(len(text), self.max_length)


class CommandNormalizer:
    """Performs conservative, non-destructive text normalization."""

    # Regex to collapse multiple spaces/tabs into a single space
    _SPACE_COLLAPSE_REGEX = re.compile(r"[^\S\r\n]+")
    # Regex to limit consecutive newlines to maximum 2
    _NEWLINE_COLLAPSE_REGEX = re.compile(r"\n{3,}")

    def normalize(self, text: str) -> str:
        """Normalizes Unicode, linebreaks, and extraneous whitespace."""
        # 1. Unicode NFKC normalization
        normalized = unicodedata.normalize("NFKC", text)

        # 2. Normalize Windows/Mac line endings to standard Unix \n
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Strip leading and trailing whitespace
        normalized = normalized.strip()

        # 4. Collapse consecutive horizontal whitespace on each line
        lines = []
        for line in normalized.split("\n"):
            collapsed_line = self._SPACE_COLLAPSE_REGEX.sub(" ", line).strip()
            lines.append(collapsed_line)

        # 5. Rejoin and collapse excess blank lines
        result = "\n".join(lines)
        result = self._NEWLINE_COLLAPSE_REGEX.sub("\n\n", result)
        return result


class CommandContextBuilder:
    """Constructs safe, lightweight runtime context metadata."""

    @staticmethod
    def build_context(source: CommandSource = CommandSource.TEXT) -> CommandContext:
        hw = app_state.hardware
        return CommandContext(
            app_version=config.version,
            active_runtime=hw.active_runtime,
            metadata={
                "source": source.value,
                "npu_present": hw.npu_present,
                "cpu_name": hw.cpu_name,
                "env": config.env
            }
        )


class CommandParser:
    """Facade orchestrating validation, normalization, and context building."""

    def __init__(self, max_length: int = 2000) -> None:
        self.validator = CommandValidator(max_length=max_length)
        self.normalizer = CommandNormalizer()
        self.context_builder = CommandContextBuilder()

    def parse(self, raw_text: str, source: CommandSource = CommandSource.TEXT) -> Tuple[str, CommandContext]:
        """Validates, normalizes, and packages context for a raw command."""
        self.validator.validate(raw_text)
        normalized = self.normalizer.normalize(raw_text)
        context = self.context_builder.build_context(source)
        return normalized, context
