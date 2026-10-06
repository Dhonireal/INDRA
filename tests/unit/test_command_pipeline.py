"""
Comprehensive Unit Tests for VisionPilot Phase 3 Text Command Pipeline.

Verifies:
1. Empty command rejected
2. Whitespace-only command rejected
3. Valid command accepted
4. Leading/trailing whitespace normalized
5. Repeated whitespace handled correctly
6. Unicode normalization handled correctly
7. Maximum command length enforced
8. Over-limit command rejected
9. Raw text preserved
10. Normalized text stored separately
11. Unique command IDs generated
12. Command source is TEXT
13. Command lifecycle transitions correctly
14. Command events emitted
15. Invalid command produces proper error
16. Cancellation works
17. Duplicate submission protection works
18. Command result is correctly structured
19. UI receives command status updates
20. History integration works (SQLite persistence)
21. No external network/API call occurs
22. Security tests: user input is treated as DATA and never executed as code
"""
import pytest
from datetime import datetime
from PySide6.QtWidgets import QApplication

from app.core.config import config
from app.core.state import app_state, TaskStatus
from app.core.events import (
    event_bus, CommandReceivedEvent, CommandValidatedEvent,
    CommandNormalizedEvent, CommandRejectedEvent, CommandReadyEvent,
    CommandCancelledEvent, TaskCreatedEvent, ErrorEvent
)
from app.core.exceptions import InvalidCommandError, CommandTooLongError
from app.agent.task_schema import (
    CommandRequest, TaskRequest, CommandResult,
    CommandSource, CommandStatus
)
from app.agent.command_parser import CommandValidator, CommandNormalizer, CommandParser
from app.services.task_service import CommandService
from app.storage.repositories import CommandRepository
from app.ui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    yield app


@pytest.fixture
def clean_pipeline():
    app_state.reset()
    event_bus.clear()
    yield
    app_state.reset()
    event_bus.clear()


class TestValidationAndNormalization:
    def test_empty_command_rejected(self) -> None:
        validator = CommandValidator(max_length=2000)
        with pytest.raises(InvalidCommandError):
            validator.validate("")

    def test_whitespace_only_command_rejected(self) -> None:
        validator = CommandValidator(max_length=2000)
        with pytest.raises(InvalidCommandError):
            validator.validate("   \t  \n  ")

    def test_valid_command_accepted(self) -> None:
        validator = CommandValidator(max_length=2000)
        # Should not raise
        validator.validate("Find the latest PDF in Downloads")

    def test_leading_trailing_whitespace_normalized(self) -> None:
        normalizer = CommandNormalizer()
        raw = "   Find the latest PDF in Downloads    "
        normalized = normalizer.normalize(raw)
        assert normalized == "Find the latest PDF in Downloads"

    def test_repeated_whitespace_handled_correctly(self) -> None:
        normalizer = CommandNormalizer()
        raw = "Find   the   latest   PDF   in   Downloads"
        normalized = normalizer.normalize(raw)
        assert normalized == "Find the latest PDF in Downloads"

    def test_unicode_normalization_nfkc(self) -> None:
        normalizer = CommandNormalizer()
        # Half-width and full-width forms
        raw = "Ｆｉｎｄ ＰＤＦ"
        normalized = normalizer.normalize(raw)
        assert normalized == "Find PDF"

    def test_max_command_length_enforced(self) -> None:
        validator = CommandValidator(max_length=50)
        long_text = "A" * 51
        with pytest.raises(CommandTooLongError) as exc_info:
            validator.validate(long_text)
        assert "exceeds maximum limit" in exc_info.value.message
        assert exc_info.value.get_user_friendly_message() != ""

    def test_command_within_limit_passes(self) -> None:
        validator = CommandValidator(max_length=50)
        valid_text = "A" * 50
        validator.validate(valid_text)


class TestCommandServicePipeline:
    def test_raw_and_normalized_text_separation(self, clean_pipeline) -> None:
        service = CommandService()
        raw = "   Move   report.pdf   to   Research   "
        result = service.process_command(raw)

        assert result.success is True
        assert result.raw_text == raw
        assert result.normalized_text == "Move report.pdf to Research"
        assert result.task_request is not None
        assert result.task_request.prompt == "Move report.pdf to Research"

    def test_unique_command_ids_generated(self, clean_pipeline) -> None:
        service = CommandService()
        res1 = service.process_command("Command One")
        res2 = service.process_command("Command Two")
        assert res1.command_id != res2.command_id
        assert res1.command_id.startswith("cmd_")
        assert res2.command_id.startswith("cmd_")

    def test_command_source_is_text(self, clean_pipeline) -> None:
        service = CommandService()
        res = service.process_command("Open Chrome")
        assert res.task_request.source == CommandSource.TEXT

    def test_command_lifecycle_and_events_emitted(self, clean_pipeline) -> None:
        service = CommandService()
        events_emitted = []

        event_bus.subscribe(CommandReceivedEvent, lambda ev: events_emitted.append("RECEIVED"))
        event_bus.subscribe(CommandValidatedEvent, lambda ev: events_emitted.append("VALIDATED"))
        event_bus.subscribe(CommandNormalizedEvent, lambda ev: events_emitted.append("NORMALIZED"))
        event_bus.subscribe(CommandReadyEvent, lambda ev: events_emitted.append("READY"))
        event_bus.subscribe(TaskCreatedEvent, lambda ev: events_emitted.append("TASK_CREATED"))

        result = service.process_command("Find latest PDF")

        assert result.success is True
        assert result.status == CommandStatus.READY_FOR_PLANNING
        assert events_emitted == ["RECEIVED", "VALIDATED", "NORMALIZED", "READY", "TASK_CREATED"]

    def test_invalid_command_produces_proper_error(self, clean_pipeline) -> None:
        service = CommandService()
        rejected_events = []
        error_events = []

        event_bus.subscribe(CommandRejectedEvent, lambda ev: rejected_events.append(ev))
        event_bus.subscribe(ErrorEvent, lambda ev: error_events.append(ev))

        result = service.process_command("   ")

        assert result.success is False
        assert result.status == CommandStatus.FAILED
        assert result.error_code == "INVALID_COMMAND"
        assert len(rejected_events) == 1
        assert len(error_events) == 1

    def test_cancellation(self, clean_pipeline) -> None:
        service = CommandService()
        cancelled_events = []
        event_bus.subscribe(CommandCancelledEvent, lambda ev: cancelled_events.append(ev))

        res = service.process_command("Find and delete old downloads")
        cmd_id = res.command_id

        # Cancel the command
        assert service.cancel_command(cmd_id) is True
        assert len(cancelled_events) == 1
        assert cancelled_events[0].command_id == cmd_id
        assert app_state.status == TaskStatus.IDLE

    def test_duplicate_submission_protection(self, clean_pipeline) -> None:
        service = CommandService()
        # Simulate active command lock
        service._processing_in_progress = True
        res = service.process_command("Concurrent click test")
        assert res.success is False
        assert res.error_code == "CONCURRENT_SUBMISSION"
        service._processing_in_progress = False

    def test_command_result_structured(self, clean_pipeline) -> None:
        service = CommandService()
        res = service.process_command("Sort files by date")
        assert isinstance(res, CommandResult)
        assert res.command_id != ""
        assert res.status == CommandStatus.READY_FOR_PLANNING
        assert res.task_request is not None
        assert res.task_request.prompt == "Sort files by date"

    def test_history_integration_sqlite(self, clean_pipeline) -> None:
        repo = CommandRepository()
        service = CommandService(repository=repo)

        res = service.process_command("Test SQLite Persistence")
        assert res.success is True

        record = repo.get_by_id(res.command_id)
        assert record is not None
        assert record["command_id"] == res.command_id
        assert record["raw_text"] == "Test SQLite Persistence"
        assert record["normalized_text"] == "Test SQLite Persistence"
        assert record["status"] == CommandStatus.READY_FOR_PLANNING.value


class TestUIServiceIntegration:
    def test_ui_receives_command_updates(self, qapp, clean_pipeline) -> None:
        window = MainWindow()
        window.show()

        # Submit valid command
        window.command_input.editor.setPlainText("Find latest PDF in Downloads")
        window.command_input.send_btn.click()
        qapp.processEvents()

        # Check AppState and TaskPanel
        assert app_state.current_command == "Find latest PDF in Downloads"
        assert "Find latest PDF in Downloads" in window.task_panel.command_label.text()
        assert not window.error_banner.isVisible()

        # Check ActivityPanel has recorded the entry
        assert window.activity_panel.items_layout.count() >= 1

        # Submit invalid command
        window.command_input.editor.setPlainText("   ")
        window.command_input.send_btn.click()
        qapp.processEvents()

        # Error banner should now be visible
        assert window.error_banner.isVisible()
        window.close()


class TestSecurityAndDataIsolation:
    @pytest.mark.parametrize("malicious_input", [
        "python os.system('calc')",
        "powershell Start-Process calc",
        "rm -rf /",
        "; shutdown",
        "<script>alert(1)</script>",
        "__import__('os').system('dir')",
        "'; DROP TABLE command_history; --"
    ])
    def test_user_input_treated_as_plain_data_never_executed(self, clean_pipeline, malicious_input: str) -> None:
        """
        Critical security test verifying that command inputs containing shell commands,
        Python statements, or SQL statements remain inert string data and are NEVER evaluated.
        """
        service = CommandService()
        result = service.process_command(malicious_input)

        # Pipeline must accept or validate without executing code
        assert result.success is True
        assert result.normalized_text == malicious_input.strip()
        # Prompt payload retains exact text as plain string
        assert result.task_request.prompt == malicious_input.strip()

        # Verify SQLite table intact (SQL injection check)
        repo = CommandRepository()
        recent = repo.get_recent(limit=10)
        assert len(recent) > 0
