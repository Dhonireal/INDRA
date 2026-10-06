"""
VisionPilot Exception Hierarchy.

Separates user-facing friendly messages from technical developer diagnostics
in strict accordance with Rule 25 (Error Handling).
"""
from typing import Optional


class VisionPilotError(Exception):
    """Base exception for all VisionPilot exceptions."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.user_message = user_message or "An unexpected issue occurred. Please check logs for details."

    def get_user_friendly_message(self) -> str:
        """Returns safe, user-friendly description without exposing stack traces."""
        return self.user_message


class DeviceError(VisionPilotError):
    """Raised when hardware detection, NPU, or GPU acceleration fails."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "Hardware accelerator or device subsystem encountered an issue."
        super().__init__(message, user_message or default_user)


class PerceptionError(VisionPilotError):
    """Raised when screen capture, UI automation tree inspection, or OCR fails."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "VisionPilot could not inspect the current screen or find the requested UI element."
        super().__init__(message, user_message or default_user)


class PlanningError(VisionPilotError):
    """Raised when the AI planner fails to generate a valid or safe plan."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "VisionPilot could not determine a valid step-by-step plan for your command."
        super().__init__(message, user_message or default_user)


class SafetyViolationError(VisionPilotError):
    """Raised when an action violates safety policies or is blocked."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "The requested action was blocked by VisionPilot's safety policy."
        super().__init__(message, user_message or default_user)


class ExecutionError(VisionPilotError):
    """Raised when computer automation action fails."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "VisionPilot was unable to complete the requested computer action."
        super().__init__(message, user_message or default_user)


class TargetNotFoundError(ExecutionError):
    """Raised when target UI control or window cannot be found."""

    def __init__(self, target_name: str, message: Optional[str] = None) -> None:
        msg = message or f"Target '{target_name}' was not found on screen."
        user_msg = f"VisionPilot could not find the '{target_name}' control on your screen."
        super().__init__(msg, user_msg)


class StaleTargetError(ExecutionError):
    """Raised when target UI control state changed or is no longer valid."""

    def __init__(self, target_name: str, reason: str = "Target state changed") -> None:
        msg = f"Target '{target_name}' is stale: {reason}"
        user_msg = f"The screen control '{target_name}' moved or changed before the action could be performed."
        super().__init__(msg, user_msg)


class PathSecurityError(SafetyViolationError):
    """Raised when a file operation accesses a protected or unsafe path."""

    def __init__(self, path: str, reason: str) -> None:
        msg = f"Path '{path}' is blocked by security policy: {reason}"
        user_msg = f"Access to '{path}' was blocked by VisionPilot's security policy."
        super().__init__(msg, user_msg)


class FileCollisionError(ExecutionError):
    """Raised when destination file exists and overwrite is not authorized."""

    def __init__(self, path: str) -> None:
        msg = f"Destination file '{path}' already exists."
        user_msg = f"A file named '{path}' already exists at destination."
        super().__init__(msg, user_msg)


class ConfirmationExpiredError(SafetyViolationError):
    """Raised when user safety confirmation timed out."""

    def __init__(self, action_id: str) -> None:
        msg = f"Confirmation for action '{action_id}' expired."
        user_msg = "The confirmation request timed out."
        super().__init__(msg, user_msg)


class VerificationError(VisionPilotError):
    """Raised when post-action verification fails to observe the expected outcome."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "VisionPilot completed the action, but could not verify the expected outcome."
        super().__init__(message, user_message or default_user)


class VoiceError(VisionPilotError):
    """Raised when microphone capture or speech-to-text fails."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "Microphone input or speech recognition could not process your voice command."
        super().__init__(message, user_message or default_user)


class InvalidCommandError(VisionPilotError):
    """Raised when user command fails validation (empty, whitespace, invalid)."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "Please enter a valid command."
        super().__init__(message, user_message or default_user)


class CommandTooLongError(InvalidCommandError):
    """Raised when user command exceeds configured maximum character length."""

    def __init__(self, length: int, max_length: int) -> None:
        message = f"Command length {length} exceeds maximum limit of {max_length} characters."
        user_message = f"Your command is too long ({length} characters). The limit is {max_length} characters."
        super().__init__(message, user_message)


class CommandCancelledError(VisionPilotError):
    """Raised when command is cancelled before or during processing."""

    def __init__(self, command_id: str) -> None:
        message = f"Command {command_id} was cancelled by user request."
        user_message = "Command was cancelled."
        super().__init__(message, user_message)


class CommandProcessingError(VisionPilotError):
    """Raised when command pipeline encounters an unrecoverable processing error."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "VisionPilot encountered an error while processing your command."
        super().__init__(message, user_message or default_user)


class VerificationError(VisionPilotError):
    """Raised when action verification cannot confirm an expected postcondition."""

    def __init__(self, message: str, user_message: Optional[str] = None) -> None:
        default_user = "VisionPilot could not verify that the expected action result occurred."
        super().__init__(message, user_message or default_user)


class VerificationTimeoutError(VerificationError):
    """Raised when waiting for a verified postcondition exceeds configured timeout."""

    def __init__(self, target_description: str, timeout_s: float) -> None:
        msg = f"Verification timed out after {timeout_s:.1f}s waiting for: {target_description}"
        user_msg = f"Timed out waiting for expected change: {target_description}"
        super().__init__(msg, user_msg)


class RecoveryLimitExceededError(VisionPilotError):
    """Raised when automated recovery attempts exceed configured safety threshold."""

    def __init__(self, action_id: str, attempts: int, max_depth: int) -> None:
        msg = f"Action [{action_id}] exceeded maximum recovery depth of {max_depth} (made {attempts} attempts)."
        user_msg = f"VisionPilot reached the safe recovery limit and paused to prevent unintended actions."
        super().__init__(msg, user_msg)
