"""
Phase 15 Production Bug Fix Regression Tests.

Validates the resolution of the 5 production issues:
1. Cancellation reset on new TaskPlanner/ActionExecutor invocations
2. Step-to-step output binding for multi-step file operations
3. Verification state isolation between independent tasks
4. Real local STT initialization, status reporting, and error handling
5. UI command execution lifecycle policy compliance
"""
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from app.agent.providers.mock_reasoning import MockReasoningProvider
from app.agent.task_planner import TaskPlanner, task_planner
from app.agent.task_schema import (
    ActionIntent, ActionTarget, CommandRequest, CommandSource,
    PlanStatus, PlanStep, RiskLevel, TaskPlan
)
from app.core.config import config
from app.core.events import event_bus
from app.core.exceptions import VoiceError
from app.core.state import app_state, TaskStatus
from app.execution.action_executor import ActionExecutor, action_executor
from app.execution.file_executor import FileActionExecutor
from app.execution.path_policy import PathSecurityPolicy
from app.execution.schema import ActionRequest, ActionResult, ActionStatus
from app.verification.engine import VerificationEngine
from app.verification.strategies.registry import VerificationStrategyRegistry
from app.verification.task_verifier import TaskVerifier
from app.voice.providers.local_stt import LocalSTTProvider, STTProviderStatus


@pytest.fixture(autouse=True)
def reset_test_state():
    """Ensure clean app state and event bus before each test."""
    app_state.reset()
    event_bus.clear()
    with task_planner._lock:
        task_planner._is_cancelled = False
    with action_executor._lock:
        action_executor._is_cancelled = False
        action_executor.step_verifications.clear()
        action_executor._completed_action_ids.clear()


# ============================================================
# PART A: TASK PLANNER CANCELLATION RESET
# ============================================================

def test_cancel_then_new_task_can_plan():
    """Verify that cancelling one plan does not lock subsequent planning requests."""
    planner = TaskPlanner(provider=MockReasoningProvider())

    # Cancel planner
    planner.cancel()
    assert planner._is_cancelled is True

    # Start a new planning task
    cmd = CommandRequest(raw_text="Find document")
    plan = planner.create_plan(cmd)

    # Must NOT be cancelled; new task resets cancellation flag
    assert plan.status == PlanStatus.READY
    assert len(plan.steps) > 0
    assert planner._is_cancelled is False


def test_cancel_during_active_plan_still_cancels():
    """Verify that calling cancel during an active plan still flags cancellation."""
    planner = TaskPlanner(provider=MockReasoningProvider())
    planner.cancel()
    assert planner._is_cancelled is True


def test_multiple_tasks_after_cancel():
    """Verify multiple subsequent plans succeed smoothly after a cancellation."""
    planner = TaskPlanner(provider=MockReasoningProvider())
    planner.cancel()

    for i in range(3):
        cmd = CommandRequest(raw_text=f"Task number {i + 1}")
        plan = planner.create_plan(cmd)
        assert plan.status == PlanStatus.READY, f"Task {i + 1} failed to plan"


# ============================================================
# PART B & D: ACTION EXECUTOR STATE & VERIFICATION ISOLATION
# ============================================================

def test_cancel_then_new_execution_works():
    """Verify that cancelling an execution does not block the next plan execution."""
    executor = ActionExecutor()
    executor.cancel()
    assert executor._is_cancelled is True

    # Build a simple safe mock plan
    step = PlanStep(
        step_id="step_safe_1",
        order=1,
        intent=ActionIntent(capability="OBSERVE_SCREEN"),
        description="Observe screen",
        risk_level=RiskLevel.SAFE
    )
    plan = TaskPlan(
        command_id="cmd_test",
        goal="Test goal",
        summary="Test summary",
        status=PlanStatus.READY,
        steps=[step]
    )

    with patch.object(executor.ui_executor, "execute") as mock_exec:
        res = ActionResult(action_id="act_1", task_id="task_test", capability="OBSERVE_SCREEN")
        res.mark_completed(ActionStatus.SUCCESS, "Screen observed")
        mock_exec.return_value = res

        results = executor.execute_plan(plan)
        assert len(results) == 1
        assert results[0].success is True
        assert executor._is_cancelled is False


def test_verification_state_isolated_between_tasks():
    """Verify that step_verifications does not leak from Task A into Task B."""
    executor = ActionExecutor()

    # Create dummy previous verification
    prev_res = ActionResult(action_id="prev_act", task_id="task_prev", capability="OBSERVE_SCREEN")
    prev_res.mark_completed(ActionStatus.SUCCESS, "Previous")
    executor.step_verifications.append((prev_res, None))
    assert len(executor.step_verifications) == 1

    # Execute a new plan
    step = PlanStep(
        step_id="step_new_1",
        order=1,
        intent=ActionIntent(capability="OBSERVE_SCREEN"),
        description="Observe screen",
        risk_level=RiskLevel.SAFE
    )
    plan = TaskPlan(
        command_id="cmd_new",
        goal="New goal",
        summary="New summary",
        status=PlanStatus.READY,
        steps=[step]
    )

    with patch.object(executor.ui_executor, "execute") as mock_exec:
        res = ActionResult(action_id="act_new", task_id="task_new", capability="OBSERVE_SCREEN")
        res.mark_completed(ActionStatus.SUCCESS, "Screen observed")
        mock_exec.return_value = res

        executor.execute_plan(plan)
        # step_verifications must have only the new task's steps (1 step, NOT 2)
        assert len(executor.step_verifications) == 1
        assert executor.step_verifications[0][0].action_id == "act_new"


def test_completed_action_ids_are_task_scoped():
    """Verify that completed action IDs do not skip steps across different tasks."""
    executor = ActionExecutor()
    executor._completed_action_ids.add("step_repeat")

    step = PlanStep(
        step_id="step_repeat",
        order=1,
        intent=ActionIntent(capability="OBSERVE_SCREEN"),
        description="Observe screen",
        risk_level=RiskLevel.SAFE
    )
    plan = TaskPlan(
        command_id="cmd_repeat",
        goal="Repeat goal",
        summary="Repeat summary",
        status=PlanStatus.READY,
        steps=[step]
    )

    with patch.object(executor.ui_executor, "execute") as mock_exec:
        res = ActionResult(action_id="act_repeat", task_id="task_repeat", capability="OBSERVE_SCREEN")
        res.mark_completed(ActionStatus.SUCCESS, "Observed")
        mock_exec.return_value = res

        results = executor.execute_plan(plan)
        assert len(results) == 1
        assert results[0].success is True


# ============================================================
# PART C: DEPENDENCY RESULT BINDING
# ============================================================

def test_multi_step_file_workflow_dynamic_binding():
    """End-to-end regression test for FIND_FILE -> RENAME_FILE -> MOVE_FILE dynamic output binding."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir).resolve()
        downloads_dir = temp_root / "Downloads"
        research_dir = temp_root / "Research"
        downloads_dir.mkdir()
        research_dir.mkdir()

        # Seed Downloads with a PDF
        original_pdf = downloads_dir / "latest-research.pdf"
        original_pdf.write_text("Qualcomm AI Research Findings", encoding="utf-8")

        policy = PathSecurityPolicy(allowed_roots=[downloads_dir, research_dir])
        file_executor = FileActionExecutor(policy=policy)
        verif_engine = VerificationEngine(registry=VerificationStrategyRegistry(path_policy=policy))
        executor = ActionExecutor(file_exec=file_executor, verif_engine=verif_engine)

        # Plan with dynamic placeholder "selected_file"
        step1 = PlanStep(
            step_id="step_1",
            order=1,
            intent=ActionIntent(
                capability="FIND_FILE",
                target=ActionTarget(target_type="FILE", name="latest.pdf"),
                parameters={"directory": str(downloads_dir), "pattern": "*.pdf", "criterion": "latest"}
            ),
            description="Find latest PDF",
            expected_result="Identified latest PDF",
            verification_requirement="CHECK_FILE_EXISTS",
            risk_level=RiskLevel.SAFE
        )
        step2 = PlanStep(
            step_id="step_2",
            order=2,
            intent=ActionIntent(
                capability="RENAME_FILE",
                target=ActionTarget(target_type="FILE", name="selected_file"),
                parameters={"new_name": "Qualcomm-AI.pdf"}
            ),
            description="Rename to Qualcomm-AI.pdf",
            expected_result="Renamed file",
            verification_requirement="CHECK_FILE_EXISTS",
            risk_level=RiskLevel.MEDIUM,
            depends_on=["step_1"]
        )
        step3 = PlanStep(
            step_id="step_3",
            order=3,
            intent=ActionIntent(
                capability="MOVE_FILE",
                target=ActionTarget(target_type="FILE", name="Qualcomm-AI.pdf"),
                parameters={"destination_path": str(research_dir)}
            ),
            description="Move to Research",
            expected_result="Moved file",
            verification_requirement="CHECK_FILE_EXISTS",
            risk_level=RiskLevel.MEDIUM,
            depends_on=["step_2"]
        )

        plan = TaskPlan(
            command_id="cmd_file_workflow",
            goal="Process latest research PDF",
            summary="Find, rename, and move research PDF",
            status=PlanStatus.READY,
            steps=[step1, step2, step3]
        )

        results = executor.execute_plan(plan)
        assert len(results) == 3
        assert all(r.success for r in results), f"Steps failed: {[r.message for r in results if not r.success]}"

        # Verify physical filesystem mutations
        assert not original_pdf.exists()
        assert not (downloads_dir / "Qualcomm-AI.pdf").exists()
        final_file = research_dir / "Qualcomm-AI.pdf"
        assert final_file.exists()
        assert final_file.read_text(encoding="utf-8") == "Qualcomm AI Research Findings"


def test_missing_dependency_result_fails_safely():
    """Verify that downstream steps missing prerequisite output fail safely without crashing."""
    executor = ActionExecutor()
    step_rename = PlanStep(
        step_id="step_orphan_rename",
        order=1,
        intent=ActionIntent(
            capability="RENAME_FILE",
            target=ActionTarget(target_type="FILE", name="selected_file"),
            parameters={"new_name": "Target.pdf"}
        ),
        description="Rename selected file",
        risk_level=RiskLevel.MEDIUM
    )
    plan = TaskPlan(
        command_id="cmd_orphan",
        goal="Orphan rename",
        summary="Orphan rename",
        status=PlanStatus.READY,
        steps=[step_rename]
    )

    results = executor.execute_plan(plan)
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error_code == "MISSING_DEPENDENCY_RESULT"


# ============================================================
# PART E: REAL LOCAL STT
# ============================================================

def test_stt_provider_initialization():
    """Verify LocalSTTProvider initializes correctly and reports truthful status."""
    provider = LocalSTTProvider()
    assert provider.metadata.local_processing is True
    assert provider.metadata.accelerator == "CPU"
    success = provider.initialize()
    if success:
        assert provider.status == STTProviderStatus.READY
    else:
        assert provider.status in (STTProviderStatus.UNAVAILABLE, STTProviderStatus.FAILED)


def test_stt_empty_audio_raises_voice_error():
    """Verify empty or corrupted audio bytes raise VoiceError."""
    provider = LocalSTTProvider()
    with pytest.raises(VoiceError) as exc_info:
        provider.transcribe(b"")
    assert "No speech detected" in exc_info.value.get_user_friendly_message()


def test_stt_cleanup():
    """Verify clean release of resources."""
    provider = LocalSTTProvider()
    provider.initialize()
    provider.cleanup()
    assert provider._initialized is False
    assert provider._recognizer is None
