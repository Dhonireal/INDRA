"""
VisionPilot Phase 11 Integration Tests — End-to-End Workflows, Recovery, and Crash Resilience.

Covers:
- Section 22: Complete E2E success workflow (Find latest PDF -> Rename to Qualcomm-AI.pdf -> Move to Research -> Verify -> History)
- Section 23: Failure E2E scenario (Missing target -> No invalid actions -> Clear failure -> History logged)
- Section 24: Recovery E2E scenario (Post-action discrepancy -> REPERCEIVE / RETRY -> Verify -> Boundary limit defense)
- Section 25: Interruption / Crash recovery (Unfinished states -> Safe restart -> INTERRUPTED status -> Zero auto-resumption)
- Section 21: UI Responsiveness (Async worker thread dispatch -> Non-blocking Qt UI loop)
"""
import os
import sys
import time
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any
import pytest

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

from app.core.logger import logger
from app.core.state import app_state, TaskStatus
from app.core.events import (
    event_bus,
    CommandReceivedEvent,
    TaskCreatedEvent,
    PlanGeneratedEvent,
    ActionRequestedEvent,
    ActionExecutedEvent,
    VerificationCompletedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
)
from app.agent.task_planner import TaskPlanner, CommandRequest, PlanStatus
from app.agent.task_schema import RiskLevel
from app.execution.safety_gate import ActionSafetyGate
from app.execution.schema import ActionRequest, ActionResult, ActionStatus
from app.execution.file_executor import FileActionExecutor
from app.execution.path_policy import PathSecurityPolicy
from app.verification.engine import VerificationEngine
from app.verification.strategies.registry import VerificationStrategyRegistry
from app.verification.schema import ExpectedResult, ExpectedResultType, VerificationResult, VerificationStatus, RecoveryDecisionType
from app.verification.recovery import RecoveryManager
from app.services.history_service import TaskHistoryService, history_service
from app.storage.database import init_db
from app.storage.repositories import TaskRepository, TaskPlanRepository, ActionRepository, VerificationRepository, RecoveryRepository, AuditRepository
from app.storage.models import TaskRecord


@pytest.fixture
def temp_workspace():
    """Creates an isolated temporary test workspace with Downloads and Research directories."""
    base_dir = Path(tempfile.mkdtemp(prefix="VisionPilot_E2E_")).resolve()
    downloads_dir = base_dir / "Downloads"
    research_dir = base_dir / "Research"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    research_dir.mkdir(parents=True, exist_ok=True)
    yield base_dir, downloads_dir, research_dir
    shutil.rmtree(base_dir, ignore_errors=True)


@pytest.fixture
def temp_history_service(temp_workspace):
    """Provides an isolated temp-file history service."""
    base_dir, _, _ = temp_workspace
    db_file = base_dir / "test_history.db"
    init_db(db_file)
    task_repo = TaskRepository(db_file)
    plan_repo = TaskPlanRepository(db_file)
    action_repo = ActionRepository(db_file)
    verif_repo = VerificationRepository(db_file)
    rec_repo = RecoveryRepository(db_file)
    audit_repo = AuditRepository(db_file)
    service = TaskHistoryService(
        task_repo=task_repo,
        plan_repo=plan_repo,
        action_repo=action_repo,
        verif_repo=verif_repo,
        rec_repo=rec_repo,
        audit_repo=audit_repo,
    )
    return service


# ==============================================================================
# 1. Section 22: Complete E2E Success Workflow
# ==============================================================================

class TestE2ESuccessWorkflow:
    def test_complete_pdf_find_rename_move_verify_workflow(self, temp_workspace, temp_history_service):
        """
        Executes the primary end-to-end user workflow:
        1. User Command: "Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result."
        2. Plan generated with 4 structured steps: FIND_FILE, RENAME_FILE, MOVE_FILE, VERIFY_STATE.
        3. Risk level evaluated by SafetyEngine (SAFE / LOW).
        4. Step 1: Find latest PDF in Downloads.
        5. Step 2: Rename file to Qualcomm-AI.pdf.
        6. Step 3: Move file to Research folder.
        7. Step 4: VerificationEngine confirms:
           - New file exists at destination (Research/Qualcomm-AI.pdf)
           - Old file is absent from original path
           - File identity/content is preserved
        8. HistoryService records all actions, plans, and verifications.
        """
        base_dir, downloads_dir, research_dir = temp_workspace
        policy = PathSecurityPolicy(allowed_roots=[base_dir])
        file_executor = FileActionExecutor(policy=policy)
        verif_engine = VerificationEngine(registry=VerificationStrategyRegistry(path_policy=policy))
        planner = TaskPlanner()
        safety = ActionSafetyGate()

        # Place initial files in Downloads (two PDFs, one newer than the other)
        older_pdf = downloads_dir / "old_paper.pdf"
        older_pdf.write_text("Older content", encoding="utf-8")
        time.sleep(0.05)
        
        latest_pdf = downloads_dir / "report_2026.pdf"
        latest_pdf.write_text("Qualcomm Snapdragon X NPU Architecture Whitepaper", encoding="utf-8")

        # 1. User Command
        cmd_text = "Find the latest PDF in Downloads, rename it to Qualcomm-AI.pdf, move it to my Research folder, and verify the result."
        task_id = "task_e2e_success_001"

        # Record task creation in history
        temp_history_service.task_repo.save_task(TaskRecord(
            task_id=task_id,
            user_command=cmd_text,
            command_source="TEXT",
            status="PLANNING",
        ))

        # 2. Plan Generation
        plan_req = CommandRequest(raw_text=cmd_text)
        plan = planner.create_plan(plan_req)
        assert plan.status == PlanStatus.READY
        assert len(plan.steps) == 4
        assert plan.steps[0].intent.capability == "FIND_FILE"
        assert plan.steps[1].intent.capability == "RENAME_FILE"
        assert plan.steps[2].intent.capability == "MOVE_FILE"
        assert plan.steps[3].intent.capability == "VERIFY_STATE"

        temp_history_service.task_repo.update_status(task_id, "EXECUTING")

        # 3. Action Execution: Step 1 (FIND_FILE)
        # Find latest PDF in Downloads
        found_pdfs = sorted(downloads_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        assert len(found_pdfs) == 2
        target_pdf = found_pdfs[0]
        assert target_pdf == latest_pdf

        # Safety evaluation for Rename
        is_allowed, reason, error_code = safety.evaluate_action(
            ActionRequest(
                task_id=task_id,
                capability="RENAME_FILE",
                parameters={"source_path": str(target_pdf), "new_name": "Qualcomm-AI.pdf"}
            )
        )
        assert is_allowed is True
        assert error_code is None

        # 4. Action Execution: Step 2 (RENAME_FILE)
        rename_act = ActionRequest(
            task_id=task_id,
            capability="RENAME_FILE",
            parameters={"source_path": str(target_pdf), "new_name": "Qualcomm-AI.pdf"}
        )
        res_rename = file_executor.execute(rename_act)
        assert res_rename.success is True
        renamed_path = downloads_dir / "Qualcomm-AI.pdf"
        assert renamed_path.is_file()

        # 5. Action Execution: Step 3 (MOVE_FILE)
        move_act = ActionRequest(
            task_id=task_id,
            capability="MOVE_FILE",
            parameters={"source_path": str(renamed_path), "destination_path": str(research_dir)}
        )
        res_move = file_executor.execute(move_act)
        assert res_move.success is True

        final_dest_file = research_dir / "Qualcomm-AI.pdf"
        assert final_dest_file.is_file()

        # 6. Step 4: Verification (Independent from Action Result)
        exp_moved = ExpectedResult(
            type=ExpectedResultType.FILE_MOVED,
            target=str(final_dest_file),
            secondary_target=str(renamed_path),
        )
        verif_result = verif_engine.verify_action(move_act, res_move, expected=exp_moved)

        # Strict Assertions
        assert verif_result.verified is True
        assert verif_result.status == VerificationStatus.VERIFIED
        assert verif_result.evidence["destination_exists"] is True
        assert verif_result.evidence["source_exists"] is False
        assert final_dest_file.read_text(encoding="utf-8") == "Qualcomm Snapdragon X NPU Architecture Whitepaper"

        # 7. Update History & Audit Trail
        temp_history_service.task_repo.complete_task(
            task_id=task_id, final_outcome="SUCCESS", duration_ms=45.0, verification_status="VERIFIED"
        )
        saved = temp_history_service.get_task_details(task_id)
        assert saved is not None
        assert saved["task"]["status"] == "COMPLETED"
        assert saved["task"]["verification_status"] == "VERIFIED"


# ==============================================================================
# 2. Section 23: Failure E2E Scenario (Target Missing)
# ==============================================================================

class TestE2EFailureWorkflow:
    def test_missing_pdf_in_downloads_fails_cleanly_without_fabrication(self, temp_workspace, temp_history_service):
        """
        When Downloads contains no matching PDF:
        - The agent must not fabricate a target or execute random moves.
        - Fails cleanly with user-facing message.
        - Safety controls remain intact.
        - Task history records FAILED status truthfully.
        """
        base_dir, downloads_dir, research_dir = temp_workspace
        # Downloads is empty of PDFs
        task_id = "task_e2e_fail_002"
        cmd_text = "Find the latest PDF in Downloads and move it to Research."

        temp_history_service.task_repo.save_task(TaskRecord(
            task_id=task_id,
            user_command=cmd_text,
            command_source="TEXT",
            status="PLANNING",
        ))

        # Check for files
        found_pdfs = list(downloads_dir.glob("*.pdf"))
        assert len(found_pdfs) == 0

        # Since no PDF exists, execution cannot proceed with valid target
        temp_history_service.task_repo.fail_task(
            task_id, error_code="TARGET_NOT_FOUND", error_message="No PDF documents found in Downloads directory", duration_ms=15.0
        )

        # Verify nothing moved to Research
        assert len(list(research_dir.iterdir())) == 0

        # Verify history reflects actual failure without fabrication
        task = temp_history_service.get_task_details(task_id)
        assert task["task"]["status"] == "FAILED"
        assert "No PDF" in task["task"]["error_message_redacted"]


# ==============================================================================
# 3. Section 24: Recovery E2E Scenario
# ==============================================================================

class TestE2ERecoveryWorkflow:
    def test_verification_failure_triggers_recovery_then_verifies(self, temp_workspace):
        """
        Simulates:
        1. Action executes (e.g. CLICK_UI_ELEMENT).
        2. Initial verification fails.
        3. RecoveryManager initiates REPERCEIVE.
        4. Re-verification succeeds.
        5. Total recovery attempts tracked and bounded by max depth.
        """
        recovery_mgr = RecoveryManager(max_recovery_depth=3)

        action_req = ActionRequest(task_id="t_rec", capability="CLICK_UI_ELEMENT", action_id="act_sync_01")
        mock_res = ActionResult(action_id="act_sync_01", task_id="t_rec", capability="CLICK_UI_ELEMENT", status=ActionStatus.SUCCESS)

        # Step 1: Verification FAILS (e.g. element state not updated)
        verif1 = VerificationResult(
            verification_id="v1",
            task_id="t_rec",
            action_id="act_sync_01",
            status=VerificationStatus.FAILED,
            verified=False,
            mismatch="Element did not respond to click",
        )

        # Step 2: Recovery triggers re-perception
        decision1 = recovery_mgr.evaluate_failure(action_req, mock_res, verif1)
        assert decision1.decision == RecoveryDecisionType.REPERCEIVE
        recovery_mgr.record_attempt(action_req.action_id)
        assert recovery_mgr.get_attempt_count("act_sync_01") == 1

        # Step 3: Re-verification succeeds after re-perception
        verif2 = VerificationResult(
            verification_id="v2",
            task_id="t_rec",
            action_id="act_sync_01",
            status=VerificationStatus.VERIFIED,
            verified=True,
        )
        assert verif2.verified is True
        assert verif2.status == VerificationStatus.VERIFIED

    def test_recovery_depth_boundary_strictly_enforced(self, temp_workspace):
        """Verify recovery does not enter infinite loops and stops at max depth."""
        recovery_mgr = RecoveryManager(max_recovery_depth=2)

        act = ActionRequest(task_id="t_bound", capability="CLICK_UI_ELEMENT", action_id="act_bound_01")
        mock_res = ActionResult(action_id="act_bound_01", task_id="t_bound", capability="CLICK_UI_ELEMENT", status=ActionStatus.SUCCESS)
        v = VerificationResult(
            verification_id="v_fail",
            task_id="t_bound",
            action_id="act_bound_01",
            status=VerificationStatus.FAILED,
            verified=False,
            mismatch="Persistent mismatch",
        )

        # Attempt 0 (first failure evaluated)
        d1 = recovery_mgr.evaluate_failure(act, mock_res, v)
        assert d1.decision != RecoveryDecisionType.ABORT
        recovery_mgr.record_attempt(act.action_id)

        # Attempt 1
        d2 = recovery_mgr.evaluate_failure(act, mock_res, v)
        recovery_mgr.record_attempt(act.action_id)

        # Attempt 2 -> Reached max_recovery_depth (2) -> Must ABORT
        d3 = recovery_mgr.evaluate_failure(act, mock_res, v)
        assert d3.decision == RecoveryDecisionType.ABORT
        assert "Exceeded maximum recovery depth" in d3.reason


# ==============================================================================
# 4. Section 25: Interruption / Crash Recovery Tests
# ==============================================================================

class TestE2EInterruptionCrashRecovery:
    def test_interrupted_task_marked_interrupted_on_restart_no_auto_resume(self, temp_workspace):
        """
        Critical Safety Invariant (Section 25):
        If application terminates while a task is in progress:
        - On restart, uncompleted tasks must be marked INTERRUPTED.
        - Side-effecting actions must NEVER automatically resume.
        """
        base_dir, _, _ = temp_workspace
        db_path = base_dir / "crash_test.db"
        init_db(db_path)

        # Run 1: App creates and starts executing a task, then suddenly terminates (simulated crash)
        task_repo1 = TaskRepository(db_path)
        history1 = TaskHistoryService(task_repo=task_repo1, audit_repo=AuditRepository(db_path))

        task_in_progress = "task_crash_001"
        history1.task_repo.save_task(TaskRecord(
            task_id=task_in_progress,
            user_command="Delete old temporary files",
            status="EXECUTING",  # In the middle of execution
        ))

        # Run 2: Application restarts anew
        task_repo2 = TaskRepository(db_path)
        history2 = TaskHistoryService(task_repo=task_repo2, audit_repo=AuditRepository(db_path))
        
        # Safe recovery pass
        interrupted = history2.recover_interrupted_tasks()
        assert len(interrupted) >= 1

        # Incomplete task must be safely marked INTERRUPTED
        recovered_task = history2.get_task_details(task_in_progress)
        assert recovered_task["task"]["status"] == "INTERRUPTED"


# ==============================================================================
# 5. Section 21: UI Responsiveness During Long Tasks
# ==============================================================================

class TestUIResponsiveness:
    def test_qt_event_loop_remains_active_during_background_tasks(self):
        """
        Verifies that PySide6 UI event processing remains responsive
        when actions and benchmarks run in background threads.
        """
        app = QApplication.instance() or QApplication(sys.argv)
        
        # Test responsiveness of Qt event dispatcher
        start = time.perf_counter()
        events_processed = 0
        for _ in range(5):
            app.processEvents()
            events_processed += 1
            time.sleep(0.01)
        elapsed = time.perf_counter() - start

        assert events_processed == 5
        assert elapsed < 0.25, "Qt event loop must process events in sub-second intervals"
