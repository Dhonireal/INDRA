"""
VisionPilot Command Service and Task Request Pipeline.

Implements the end-to-end Phase 3 text command pipeline:
Validates, normalizes, contextualizes, and structures commands into TaskRequests.
Publishes lifecycle events, updates application state, and stores records in SQLite.
Does NOT execute AI reasoning or computer actions (Phase 6+).
"""
import threading
from typing import Optional, Dict, Any
from app.core.config import config
from app.core.logger import logger
from app.core.state import app_state, TaskStatus
from app.core.events import (
    event_bus, CommandReceivedEvent, CommandValidatedEvent,
    CommandNormalizedEvent, CommandRejectedEvent, CommandReadyEvent,
    CommandCancelledEvent, TaskCreatedEvent, ErrorEvent
)
from app.core.exceptions import (
    InvalidCommandError, CommandTooLongError, CommandCancelledError,
    CommandProcessingError, VisionPilotError
)
from app.agent.task_schema import (
    CommandRequest, TaskRequest, CommandResult,
    CommandSource, CommandStatus, CommandContext
)
from app.agent.command_parser import CommandValidator, CommandNormalizer, CommandContextBuilder
from app.storage.repositories import command_repository, CommandRepository


class CommandService:
    """Service orchestrating the lifecycle of incoming user commands."""

    def __init__(self, repository: Optional[CommandRepository] = None) -> None:
        self.validator = CommandValidator(
            max_length=config.command.max_command_length,
            min_length=config.command.min_command_length
        )
        self.normalizer = CommandNormalizer()
        self.context_builder = CommandContextBuilder()
        self.repository = repository or command_repository

        self._lock = threading.Lock()
        self._active_commands: Dict[str, CommandRequest] = {}
        self._processing_in_progress = False

    def process_command(
        self,
        raw_text: str,
        source: CommandSource = CommandSource.TEXT
    ) -> CommandResult:
        """Processes a raw user command through validation, normalization, and task creation."""
        with self._lock:
            # Duplicate submission protection
            if self._processing_in_progress:
                logger.warning("Duplicate command submission rejected: a command is already being accepted.")
                return CommandResult(
                    success=False,
                    command_id="",
                    status=CommandStatus.FAILED,
                    message="A command is already being processed. Please wait.",
                    error_code="CONCURRENT_SUBMISSION",
                    raw_text=raw_text
                )
            self._processing_in_progress = True

        cmd = CommandRequest(raw_text=raw_text, source=source)
        with self._lock:
            self._active_commands[cmd.command_id] = cmd

        try:
            logger.info(f"Processing command [{cmd.command_id}] from source '{source.value}'")
            event_bus.publish(CommandReceivedEvent(
                command_id=cmd.command_id,
                raw_text=raw_text,
                source=source.value
            ))

            # 1. Validation Step
            cmd.mark_status(CommandStatus.VALIDATING)
            try:
                self.validator.validate(raw_text)
                event_bus.publish(CommandValidatedEvent(
                    command_id=cmd.command_id,
                    raw_text=raw_text,
                    length=len(raw_text)
                ))
            except (InvalidCommandError, CommandTooLongError) as val_err:
                cmd.mark_status(CommandStatus.FAILED)
                error_code = "COMMAND_TOO_LONG" if isinstance(val_err, CommandTooLongError) else "INVALID_COMMAND"
                user_msg = val_err.get_user_friendly_message()
                logger.warning(f"Command validation failed [{cmd.command_id}]: {val_err.message}")

                event_bus.publish(CommandRejectedEvent(
                    command_id=cmd.command_id,
                    raw_text=raw_text,
                    reason=val_err.message,
                    error_code=error_code
                ))
                event_bus.publish(ErrorEvent(
                    task_id=cmd.command_id,
                    user_message=user_msg,
                    technical_details=str(val_err)
                ))

                if config.command.enable_history_persistence:
                    self.repository.save(cmd)
                    self.repository.update_status(cmd.command_id, CommandStatus.FAILED, error_code, val_err.message)

                return CommandResult(
                    success=False,
                    command_id=cmd.command_id,
                    status=CommandStatus.FAILED,
                    message=user_msg,
                    error_code=error_code,
                    raw_text=raw_text
                )

            # Check if cancelled during validation
            if cmd.is_cancelled:
                return self._build_cancelled_result(cmd)

            # 2. Normalization Step
            cmd.mark_status(CommandStatus.NORMALIZING)
            normalized = self.normalizer.normalize(raw_text)
            cmd.normalized_text = normalized
            event_bus.publish(CommandNormalizedEvent(
                command_id=cmd.command_id,
                raw_text=raw_text,
                normalized_text=normalized
            ))

            # 3. Context & Structured Task Request Creation
            cmd.mark_status(CommandStatus.QUEUED)
            context = self.context_builder.build_context(source)
            cmd.context = context

            task_request = TaskRequest(
                command_id=cmd.command_id,
                prompt=normalized,
                source=source,
                context=context
            )

            cmd.mark_status(CommandStatus.READY_FOR_PLANNING)
            logger.info(f"Command [{cmd.command_id}] normalized and structured as TaskRequest [{task_request.task_id}]")

            # Persist to repository
            if config.command.enable_history_persistence:
                self.repository.save(cmd, task_request.task_id)

            # Update Application State
            app_state.set_task(task_request.task_id, normalized)
            app_state.update_status(
                TaskStatus.ANALYZING,
                f"Command accepted. Ready for task planning."
            )

            # Publish Task and Command Events
            event_bus.publish(CommandReadyEvent(
                command_id=cmd.command_id,
                task_id=task_request.task_id,
                prompt=normalized
            ))
            event_bus.publish(TaskCreatedEvent(
                task_id=task_request.task_id,
                command=normalized,
                source=source.value.lower()
            ))

            return CommandResult(
                success=True,
                command_id=cmd.command_id,
                status=CommandStatus.READY_FOR_PLANNING,
                message="Command successfully parsed and prepared for task planner.",
                task_request=task_request,
                raw_text=raw_text,
                normalized_text=normalized
            )

        except Exception as e:
            logger.exception(f"Unexpected error in command pipeline [{cmd.command_id}]: {e}")
            cmd.mark_status(CommandStatus.FAILED)
            err_msg = "VisionPilot encountered an error while processing your command."
            event_bus.publish(ErrorEvent(
                task_id=cmd.command_id,
                user_message=err_msg,
                technical_details=str(e)
            ))
            return CommandResult(
                success=False,
                command_id=cmd.command_id,
                status=CommandStatus.FAILED,
                message=err_msg,
                error_code="INTERNAL_ERROR",
                raw_text=raw_text
            )
        finally:
            with self._lock:
                self._processing_in_progress = False

    def cancel_command(self, command_id: str) -> bool:
        """Cancels an active or queued command."""
        with self._lock:
            cmd = self._active_commands.get(command_id)
            if not cmd:
                # If command_id matches current task in app_state
                if app_state.current_task_id == command_id:
                    app_state.reset()
                    return True
                return False

            cmd.mark_status(CommandStatus.CANCELLED)

        logger.info(f"Command [{command_id}] marked as CANCELLED.")
        event_bus.publish(CommandCancelledEvent(command_id=command_id))

        if config.command.enable_history_persistence:
            self.repository.update_status(command_id, CommandStatus.CANCELLED, error_code="CANCELLED")

        app_state.reset()
        return True

    def _build_cancelled_result(self, cmd: CommandRequest) -> CommandResult:
        return CommandResult(
            success=False,
            command_id=cmd.command_id,
            status=CommandStatus.CANCELLED,
            message="Command was cancelled.",
            error_code="CANCELLED",
            raw_text=cmd.raw_text
        )


# Global command service instance
command_service = CommandService()
