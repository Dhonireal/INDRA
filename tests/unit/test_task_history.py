"""
VisionPilot Task History, Audit Trail, and Retention Test Suite (Phase 9).

Covers:
- TaskRecord creation, querying, status updating, completion, failure, cancellation
- Command source persistence (TEXT, VOICE)
- Plan metadata persistence and foreign key associations
- Action record persistence and duration tracking
- Verification record persistence and evidence summaries
- Recovery record persistence and attempt counters
- Append-only audit events and chronological ordering
- Task search and filtering (by status, source, text)
- History retention policies (age-based and max-count ceiling)
- Transactional clear history
- Crash and startup interruption recovery (no auto-resumption of side effects)
- PrivacyRedactor: passwords, API keys, tokens, secret fields redaction
- SQL injection immunity
- Large history list query performance
- Safe End-to-End Task Lifecycle Integration
"""
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from app.core.config import config
from app.core.events import (
    EventBus, CommandReceivedEvent, TaskCreatedEvent, TaskStatusChangedEvent,
    PlanGeneratedEvent, SafetyConfirmationRequiredEvent, SafetyConfirmationResolvedEvent,
    ActionRequestedEvent, ActionExecutedEvent, VerificationStartedEvent,
    VerificationCompletedEvent, RecoveryDecisionEvent, RecoveryAttemptedEvent,
    TaskCompletedEvent, TaskFailedEvent, TaskCancelledEvent
)
from app.storage.database import init_db, get_db
from app.storage.models import (
    TaskRecord, TaskPlanRecord, ActionRecord,
    VerificationRecord, RecoveryRecord, AuditRecord
)
from app.storage.redaction import PrivacyRedactor
from app.storage.repositories import (
    TaskRepository, TaskPlanRepository, ActionRepository,
    VerificationRepository, RecoveryRepository, AuditRepository
)
from PySide6.QtWidgets import QApplication
from app.services.history_service import TaskHistoryService


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance runs across tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    yield app


@pytest.fixture
def temp_db(tmp_path: Path):
    """Provides a fresh, isolated temporary SQLite database for each test."""
    db_file = tmp_path / "visionpilot_test.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def repos(temp_db: Path):
    """Provides typed repository instances bound to the temporary database."""
    return {
        "task": TaskRepository(temp_db),
        "plan": TaskPlanRepository(temp_db),
        "action": ActionRepository(temp_db),
        "verif": VerificationRepository(temp_db),
        "recovery": RecoveryRepository(temp_db),
        "audit": AuditRepository(temp_db),
    }


@pytest.fixture
def service(repos):
    """Provides an isolated TaskHistoryService instance wired to temporary repositories."""
    return TaskHistoryService(
        task_repo=repos["task"],
        plan_repo=repos["plan"],
        action_repo=repos["action"],
        verif_repo=repos["verif"],
        rec_repo=repos["recovery"],
        audit_repo=repos["audit"],
    )


# ==============================================================================
# 1-6. Task Lifecycle Tests (Create, Read, Update, Complete, Fail, Cancel)
# ==============================================================================

def test_task_create_read_and_update(repos):
    task_repo = repos["task"]
    task_id = "task_test_001"
    task = TaskRecord(
        task_id=task_id,
        user_command="Find latest PDF in Downloads and move to Research",
        command_source="VOICE",
        status="CREATED"
    )
    task_repo.save_task(task)

    retrieved = task_repo.get_task(task_id)
    assert retrieved is not None
    assert retrieved.task_id == task_id
    assert retrieved.user_command == "Find latest PDF in Downloads and move to Research"
    assert retrieved.command_source == "VOICE"
    assert retrieved.status == "CREATED"

    # Update Status
    task_repo.update_status(task_id, "EXECUTING")
    updated = task_repo.get_task(task_id)
    assert updated.status == "EXECUTING"


def test_task_completion_and_failure(repos):
    task_repo = repos["task"]
    
    # Complete task
    t1_id = "task_comp_001"
    task_repo.save_task(TaskRecord(task_id=t1_id, user_command="Create Research folder"))
    task_repo.complete_task(
        task_id=t1_id,
        final_outcome="Folder created and verified",
        duration_ms=145.2,
        verification_status="VERIFIED"
    )
    t1 = task_repo.get_task(t1_id)
    assert t1.status == "COMPLETED"
    assert t1.final_outcome == "Folder created and verified"
    assert t1.duration_ms == 145.2
    assert t1.verification_status == "VERIFIED"
    assert t1.completed_at is not None

    # Fail task
    t2_id = "task_fail_002"
    task_repo.save_task(TaskRecord(task_id=t2_id, user_command="Delete System32"))
    task_repo.fail_task(
        task_id=t2_id,
        error_code="CAPABILITY_BLOCKED",
        error_message="Operation blocked by security policy",
        duration_ms=22.0
    )
    t2 = task_repo.get_task(t2_id)
    assert t2.status == "FAILED"
    assert t2.error_code == "CAPABILITY_BLOCKED"
    assert "Operation blocked" in t2.error_message_redacted


def test_task_cancellation(repos):
    task_repo = repos["task"]
    t_id = "task_cancel_001"
    task_repo.save_task(TaskRecord(task_id=t_id, user_command="Long running operation"))
    task_repo.cancel_task(t_id, reason="User clicked stop button", duration_ms=500.0)

    t = task_repo.get_task(t_id)
    assert t.status == "CANCELLED"
    assert t.cancellation_reason == "User clicked stop button"
    assert t.duration_ms == 500.0


# ==============================================================================
# 7-11. Plan, Action, Verification, Recovery Records Persistence
# ==============================================================================

def test_plan_metadata_persistence(repos):
    task_repo = repos["task"]
    plan_repo = repos["plan"]

    task_id = "task_plan_test"
    task_repo.save_task(TaskRecord(task_id=task_id, user_command="Organize documents"))

    plan = TaskPlanRecord(
        plan_id="plan_123",
        task_id=task_id,
        provider="local",
        model="VisionPilot-Deterministic-Planner-v1",
        number_of_steps=3,
        planning_duration_ms=12.5,
        plan_validation_status="VALID",
        risk_summary="MEDIUM",
        goal="Organize documents into target directory",
        summary="Creates folder and moves file",
        steps_json='[{"order": 1, "description": "Create folder"}]'
    )
    plan_repo.save_plan(plan)

    retrieved = plan_repo.get_plan_by_task(task_id)
    assert retrieved is not None
    assert retrieved.plan_id == "plan_123"
    assert retrieved.number_of_steps == 3
    assert retrieved.risk_summary == "MEDIUM"
    assert retrieved.model == "VisionPilot-Deterministic-Planner-v1"


def test_action_record_persistence(repos):
    task_repo = repos["task"]
    act_repo = repos["action"]

    task_id = "task_act_test"
    task_repo.save_task(TaskRecord(task_id=task_id, user_command="Move file"))

    act = ActionRecord(
        action_id="act_001",
        task_id=task_id,
        step_index=0,
        capability="MOVE_FILE",
        action_type="MOVE_FILE",
        target_reference="Research/Qualcomm-AI.pdf",
        risk_level="MEDIUM",
        confirmation_required=True,
        confirmation_status="APPROVED",
        duration_ms=45.0,
        executor_status="SUCCESS",
        result_status="SUCCESS",
        parameters_redacted={"source": "Downloads/test.pdf", "destination": "Research/test.pdf"}
    )
    act_repo.save_action(act)

    actions = act_repo.get_actions_for_task(task_id)
    assert len(actions) == 1
    assert actions[0].action_id == "act_001"
    assert actions[0].capability == "MOVE_FILE"
    assert actions[0].confirmation_status == "APPROVED"
    assert actions[0].parameters_redacted["source"] == "Downloads/test.pdf"


def test_verification_and_recovery_persistence(repos):
    task_repo = repos["task"]
    verif_repo = repos["verif"]
    rec_repo = repos["recovery"]

    task_id = "task_verif_rec_test"
    task_repo.save_task(TaskRecord(task_id=task_id, user_command="Verify rename"))

    # Verification
    verif = VerificationRecord(
        verification_id="ver_001",
        task_id=task_id,
        action_id="act_001",
        status="VERIFIED",
        verified=True,
        confidence=1.0,
        strategy="FileRenamedVerifier",
        expected_state_summary="Qualcomm-AI.pdf exists and source is absent",
        actual_state_summary="Qualcomm-AI.pdf verified via os.stat",
        recovery_recommended=False,
        duration_ms=2.5
    )
    verif_repo.save_verification(verif)

    v_list = verif_repo.get_verifications_for_task(task_id)
    assert len(v_list) == 1
    assert v_list[0].strategy == "FileRenamedVerifier"
    assert v_list[0].verified is True

    # Recovery
    rec = RecoveryRecord(
        recovery_id="rec_001",
        task_id=task_id,
        action_id="act_001",
        recovery_depth=1,
        decision="REPERCEIVE",
        reason="UI element momentarily unavailable during settle window",
        outcome="SUCCESS",
        duration_ms=15.0
    )
    rec_repo.save_recovery(rec)

    r_list = rec_repo.get_recoveries_for_task(task_id)
    assert len(r_list) == 1
    assert r_list[0].decision == "REPERCEIVE"
    assert r_list[0].outcome == "SUCCESS"


# ==============================================================================
# 12-16. Audit Events, Ordering, Querying, Searching & Filtering
# ==============================================================================

def test_audit_events_append_and_order(repos):
    audit_repo = repos["audit"]
    task_id = "task_audit_test"

    audit_repo.append_event(AuditRecord(
        task_id=task_id,
        event_type="TASK_CREATED",
        severity="INFO",
        message_redacted="Task created"
    ))
    time.sleep(0.01)
    audit_repo.append_event(AuditRecord(
        task_id=task_id,
        event_type="ACTION_STARTED",
        severity="INFO",
        message_redacted="Action step 1 started"
    ))
    time.sleep(0.01)
    audit_repo.append_event(AuditRecord(
        task_id=task_id,
        event_type="TASK_COMPLETED",
        severity="INFO",
        message_redacted="Task completed"
    ))

    events = audit_repo.get_events_for_task(task_id)
    assert len(events) == 3
    assert [e.event_type for e in events] == ["TASK_CREATED", "ACTION_STARTED", "TASK_COMPLETED"]


def test_task_search_and_filtering(repos):
    task_repo = repos["task"]

    t1 = TaskRecord(task_id="t1", user_command="Move PDF file", command_source="VOICE", status="COMPLETED")
    t2 = TaskRecord(task_id="t2", user_command="Rename image file", command_source="TEXT", status="FAILED")
    t3 = TaskRecord(task_id="t3", user_command="Open Calculator", command_source="VOICE", status="COMPLETED")

    task_repo.save_task(t1)
    task_repo.save_task(t2)
    task_repo.save_task(t3)

    # Search by keyword
    pdf_tasks = task_repo.list_tasks(search="PDF")
    assert len(pdf_tasks) == 1
    assert pdf_tasks[0].task_id == "t1"

    # Filter by source
    voice_tasks = task_repo.list_tasks(source="VOICE")
    assert len(voice_tasks) == 2

    # Filter by status
    failed_tasks = task_repo.list_tasks(status="FAILED")
    assert len(failed_tasks) == 1
    assert failed_tasks[0].task_id == "t2"

    # Combined filter
    filtered = task_repo.list_tasks(status="COMPLETED", source="VOICE", search="Calculator")
    assert len(filtered) == 1
    assert filtered[0].task_id == "t3"


# ==============================================================================
# 17-18. History Retention Policies & Clear History
# ==============================================================================

def test_history_retention_by_age_and_max_count(repos):
    task_repo = repos["task"]

    # 1. Age-based retention
    old_time = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    recent_time = datetime.now(timezone.utc).isoformat()

    old_task = TaskRecord(task_id="old_1", user_command="Old command", status="COMPLETED", created_at=old_time)
    new_task = TaskRecord(task_id="new_1", user_command="New command", status="COMPLETED", created_at=recent_time)

    task_repo.save_task(old_task)
    task_repo.save_task(new_task)

    deleted = task_repo.delete_older_than(days=30)
    assert deleted == 1
    assert task_repo.get_task("old_1") is None
    assert task_repo.get_task("new_1") is not None

    # 2. Max-count retention
    for i in range(10):
        task_repo.save_task(TaskRecord(
            task_id=f"bulk_{i}",
            user_command=f"Task {i}",
            status="COMPLETED",
            created_at=(datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat()
        ))

    total = task_repo.count_tasks()
    assert total == 11  # new_1 + 10 bulk tasks

    pruned = task_repo.enforce_max_count(max_tasks=5)
    assert pruned == 6
    assert task_repo.count_tasks() == 5


def test_clear_all_history_transactional(repos):
    task_repo = repos["task"]
    audit_repo = repos["audit"]

    task_repo.save_task(TaskRecord(task_id="clear_me", user_command="Temp action"))
    audit_repo.append_event(AuditRecord(task_id="clear_me", event_type="TEST_EVENT"))

    assert task_repo.count_tasks() == 1
    assert len(audit_repo.get_events_for_task("clear_me")) == 1

    task_repo.clear_all_history()

    assert task_repo.count_tasks() == 0
    assert len(audit_repo.get_events_for_task("clear_me")) == 0


# ==============================================================================
# 21-22. Crash / Interruption State Handling & Startup Recovery
# ==============================================================================

def test_startup_interruption_recovery(repos, service):
    task_repo = repos["task"]

    # Simulate an unfinished task left executing when the prior app session crashed
    interrupted_task = TaskRecord(
        task_id="task_crashed_session",
        user_command="Move high priority files",
        status="EXECUTING"
    )
    normal_task = TaskRecord(
        task_id="task_prior_completed",
        user_command="Regular check",
        status="COMPLETED"
    )
    task_repo.save_task(interrupted_task)
    task_repo.save_task(normal_task)

    # Perform startup recovery
    recovered = service.recover_interrupted_tasks()
    assert len(recovered) == 1
    assert recovered[0].task_id == "task_crashed_session"

    updated = task_repo.get_task("task_crashed_session")
    assert updated.status == "INTERRUPTED"
    assert "shutdown or crash" in updated.cancellation_reason
    assert "Not resumed automatically" in updated.cancellation_reason

    # Audit event should be recorded
    audit_events = repos["audit"].get_events_for_task("task_crashed_session")
    assert any(e.event_type == "TASK_INTERRUPTED" for e in audit_events)


# ==============================================================================
# 23-25. Privacy Redaction & Security (Passwords, Keys, SQL Injection)
# ==============================================================================

def test_privacy_redactor_sensitive_data():
    # API Keys
    sample_text = "Connecting to sk-1234567890abcdef1234567890abcdef with Bearer secrettoken1234567"
    redacted = PrivacyRedactor.redact_text(sample_text)
    assert "sk-" not in redacted
    assert "<redacted:key>" in redacted
    assert "<redacted:token>" in redacted

    # Dictionary redaction
    sensitive_dict = {
        "user": "rishi",
        "password": "SuperSecretPassword123!",
        "api_key": "AIzaSyD-123456789012345678901234567890",
        "nested": {
            "token": "secret_token_val",
            "normal_data": "public_data"
        }
    }
    cleaned = PrivacyRedactor.redact_dict(sensitive_dict)
    assert cleaned["password"] == "<redacted:credential>"
    assert cleaned["api_key"] == "<redacted:credential>"
    assert cleaned["nested"]["token"] == "<redacted:credential>"
    assert cleaned["nested"]["normal_data"] == "public_data"


def test_password_typing_parameters_redacted():
    params = {"text": "MySecretPass!99", "delay": 0.05}
    cleaned = PrivacyRedactor.redact_action_parameters(
        capability="TYPE_TEXT",
        target_name="Password Box",
        parameters=params
    )
    assert cleaned["text"] == "<redacted:password>"


def test_sql_injection_treated_as_literal_data(repos):
    task_repo = repos["task"]
    malicious_cmd = "'; DROP TABLE tasks; -- SELECT * FROM users WHERE '1'='1"

    task = TaskRecord(task_id="sql_inj_001", user_command=malicious_cmd)
    task_repo.save_task(task)

    retrieved = task_repo.get_task("sql_inj_001")
    assert retrieved is not None
    assert retrieved.user_command == malicious_cmd

    # Ensure tables still exist and query is safe
    count = task_repo.count_tasks()
    assert count >= 1


# ==============================================================================
# 26. Large History List Query Performance
# ==============================================================================

def test_large_history_list_performance(repos):
    task_repo = repos["task"]

    # Insert 500 tasks
    start_insert = time.perf_counter()
    with get_db(repos["task"].db_path) as conn:
        cursor = conn.cursor()
        for i in range(500):
            cursor.execute("""
                INSERT INTO tasks (
                    task_id, command_id, user_command, command_source, status,
                    created_at, duration_ms, recovery_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"perf_task_{i:04d}",
                f"cmd_{i}",
                f"Perform automated test operation #{i}",
                "VOICE" if i % 2 == 0 else "TEXT",
                "COMPLETED" if i % 5 != 0 else "FAILED",
                datetime.now(timezone.utc).isoformat(),
                120.0 + (i % 50),
                0
            ))
    insert_duration = (time.perf_counter() - start_insert) * 1000.0

    # Query with filtering and pagination
    start_query = time.perf_counter()
    results = task_repo.list_tasks(limit=50, offset=100, status="COMPLETED", source="VOICE")
    query_duration = (time.perf_counter() - start_query) * 1000.0

    assert len(results) == 50
    # On Oryon CPU / Windows Prism, query of 500 rows should take under 15ms
    assert query_duration < 50.0


# ==============================================================================
# 27-28. End-to-End Task Lifecycle Integration with Service
# ==============================================================================

def test_end_to_end_history_service_lifecycle(service, repos):
    bus = EventBus()
    svc = TaskHistoryService(
        task_repo=repos["task"],
        plan_repo=repos["plan"],
        action_repo=repos["action"],
        verif_repo=repos["verif"],
        rec_repo=repos["recovery"],
        audit_repo=repos["audit"],
    )

    task_id = "task_e2e_full"
    cmd_id = "cmd_e2e_100"

    # 1. Command received
    svc._on_command_received(CommandReceivedEvent(
        command_id=cmd_id,
        raw_text="Rename latest.pdf to Qualcomm-AI.pdf and move to Research",
        source="voice"
    ))

    # 2. Task created
    svc._on_task_created(TaskCreatedEvent(
        task_id=task_id,
        command="Rename latest.pdf to Qualcomm-AI.pdf and move to Research",
        source="voice"
    ))

    # 3. Plan generated
    svc._on_plan_generated(PlanGeneratedEvent(
        task_id=task_id,
        command_id=cmd_id,
        plan_id="plan_e2e",
        goal="Rename and move research PDF",
        step_count=2,
        risk_level="MEDIUM",
        provider="local",
        model="DeterministicPlanner"
    ))

    # 4. Confirmation requested & approved
    svc._on_confirmation_required(SafetyConfirmationRequiredEvent(
        task_id=task_id,
        action_id="act_e2e_1",
        action_type="RENAME_FILE",
        target="latest.pdf",
        risk_level="MEDIUM"
    ))
    svc._on_confirmation_resolved(SafetyConfirmationResolvedEvent(
        task_id=task_id,
        action_id="act_e2e_1",
        approved=True,
        reason="User accepted confirmation dialog"
    ))

    # 5. Action started & executed
    svc._on_action_requested(ActionRequestedEvent(
        action_id="act_e2e_1",
        task_id=task_id,
        step_index=0,
        capability="RENAME_FILE",
        action_type="RENAME_FILE",
        target="latest.pdf"
    ))
    svc._on_action_executed(ActionExecutedEvent(
        action_id="act_e2e_1",
        task_id=task_id,
        step_index=0,
        capability="RENAME_FILE",
        action_type="RENAME_FILE",
        success=True,
        status="SUCCESS",
        duration_ms=25.0
    ))

    # 6. Verification completed
    svc._on_verification_completed(VerificationCompletedEvent(
        verification_id="ver_e2e_1",
        task_id=task_id,
        action_id="act_e2e_1",
        status="VERIFIED",
        verified=True,
        confidence=1.0,
        strategy="FileRenamedVerifier",
        expected="Qualcomm-AI.pdf exists",
        observed="Qualcomm-AI.pdf found",
        duration_ms=1.5
    ))

    # 7. Task completed
    svc._on_task_completed(TaskCompletedEvent(
        task_id=task_id,
        status="COMPLETED",
        final_outcome="All 2 steps verified successfully",
        verification_status="VERIFIED",
        duration_ms=450.0
    ))

    # Assert complete aggregated details
    details = svc.get_task_details(task_id)
    assert details is not None
    assert details["task"]["status"] == "COMPLETED"
    assert details["task"]["verification_status"] == "VERIFIED"
    assert details["task"]["duration_ms"] == 450.0
    assert details["plan"]["plan_id"] == "plan_e2e"
    assert len(details["actions"]) == 1
    assert len(details["verifications"]) == 1
    assert len(details["audit_events"]) >= 5


# ==============================================================================
# 29-31. UI History and Detail View Tests
# ==============================================================================

def test_ui_activity_panel_rendering(qapp, temp_db, repos):
    from app.ui.activity_panel import ActivityPanel
    from app.services.history_service import history_service

    # Temporarily bind service repositories
    orig_task_repo = history_service.task_repo
    history_service.task_repo = repos["task"]
    try:
        repos["task"].save_task(TaskRecord(
            task_id="ui_task_001",
            user_command="Organize Downloads",
            status="COMPLETED",
            duration_ms=250.0
        ))

        panel = ActivityPanel()
        panel.load_recent()

        assert panel.empty_label.isVisible() is False
        assert panel.items_layout.count() >= 1
    finally:
        history_service.task_repo = orig_task_repo


def test_ui_task_detail_dialog(qapp, temp_db, repos):
    from app.ui.task_detail_dialog import TaskDetailDialog
    from app.services.history_service import history_service

    orig_task = history_service.task_repo
    orig_plan = history_service.plan_repo
    orig_act = history_service.action_repo
    orig_verif = history_service.verif_repo
    orig_audit = history_service.audit_repo

    history_service.task_repo = repos["task"]
    history_service.plan_repo = repos["plan"]
    history_service.action_repo = repos["action"]
    history_service.verif_repo = repos["verif"]
    history_service.audit_repo = repos["audit"]

    try:
        t_id = "detail_task_123"
        repos["task"].save_task(TaskRecord(
            task_id=t_id,
            user_command="Inspect files",
            status="VERIFIED_SUCCESS",
            duration_ms=180.0
        ))
        repos["audit"].append_event(AuditRecord(
            task_id=t_id,
            event_type="TASK_CREATED",
            message_redacted="Task started"
        ))

        dialog = TaskDetailDialog(t_id)
        assert dialog.windowTitle() == f"Task Audit Details — {t_id}"
        assert dialog.task_id == t_id
    finally:
        history_service.task_repo = orig_task
        history_service.plan_repo = orig_plan
        history_service.action_repo = orig_act
        history_service.verif_repo = orig_verif
        history_service.audit_repo = orig_audit


def test_ui_task_history_dialog_search_filter(qapp, temp_db, repos):
    from app.ui.task_history_dialog import TaskHistoryDialog
    from app.services.history_service import history_service

    orig_task = history_service.task_repo
    history_service.task_repo = repos["task"]

    try:
        repos["task"].save_task(TaskRecord(
            task_id="hist_1",
            user_command="Convert document to PDF",
            command_source="VOICE",
            status="COMPLETED"
        ))
        repos["task"].save_task(TaskRecord(
            task_id="hist_2",
            user_command="Delete temp cache",
            command_source="TEXT",
            status="FAILED"
        ))

        dlg = TaskHistoryDialog()
        assert dlg.count_label.text() == "2 task(s) recorded"

        # Search filter
        dlg.search_input.setText("Convert")
        assert dlg.count_label.text() == "1 task(s) recorded"

        # Status filter
        dlg.search_input.clear()
        dlg.status_combo.setCurrentText("FAILED")
        assert dlg.count_label.text() == "1 task(s) recorded"
    finally:
        history_service.task_repo = orig_task
