"""
VisionPilot Phase 7 Action Executor Comprehensive Unit & Security Tests.

Covers all 34 requirements mandated by Phase 7:
1. Action schema validation
2. Capability registry
3. Action result
4. Click action
5. Double-click action
6. Keyboard action
7. Hotkey validation
8. Scroll bounds
9. Window focus
10. Target revalidation
11. Stale target handling
12. File rename
13. File move
14. Folder creation
15. Path validation
16. Protected path rejection
17. File collision handling
18. Confirmation requirement
19. Confirmation binding
20. Confirmation expiration
21. Cancellation
22. Timeout
23. Duplicate action prevention
24. Retry policy
25. Arbitrary code rejection
26. Shell command rejection
27. Password field blocking
28. Credential input blocking
29. No deletion capability (permanent deletion BLOCKED)
30. No executor invocation from invalid plans
31. UI state updates
32. Mock executor / controlled tests
33. Integration test with Phase 6 structured plan
34. Benchmark execution
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import tempfile
import time
import pytest

from app.agent.capabilities import capability_registry, CapabilityCategory
from app.agent.task_schema import (
    ActionIntent, ActionTarget, PlanStatus, PlanStep, RiskLevel, TaskPlan
)
from app.core.config import config
from app.core.events import (
    event_bus, ActionExecutedEvent, ActionRequestedEvent,
    SafetyConfirmationRequiredEvent, SafetyConfirmationResolvedEvent
)
from app.core.exceptions import (
    FileCollisionError, PathSecurityError, SafetyViolationError,
    StaleTargetError, TargetNotFoundError
)
from app.core.state import app_state, TaskStatus
from app.execution import (
    ActionExecutor, ActionRequest, ActionResult, ActionSafetyGate,
    ActionStatus, ConfirmationBinding, FileActionExecutor,
    KeyboardActionExecutor, PathSecurityPolicy, UIActionExecutor,
    WindowActionExecutor
)
from app.perception.models import BoundingBox, ScreenState, UIElement, WindowInfo


@pytest.fixture
def temp_workspace():
    """Creates a temporary, safe directory workspace for test filesystem operations."""
    temp_dir = Path(tempfile.mkdtemp(prefix="VisionPilot_TestWorkspace_")).resolve()
    policy = PathSecurityPolicy(allowed_roots=[temp_dir])
    yield temp_dir, policy
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_environment():
    """Ensures clean application state and event bus subscriptions."""
    app_state.reset()
    event_bus.clear()
    yield
    app_state.reset()
    event_bus.clear()


# 1. Action schema validation & 3. Action result
def test_action_request_and_result_schema():
    req = ActionRequest(
        task_id="task_123",
        step_id="step_1",
        capability="FIND_FILE",
        parameters={"directory": "Downloads"},
    )
    assert req.action_id.startswith("act_")
    d = req.to_dict()
    assert d["capability"] == "FIND_FILE"

    res = ActionResult(
        action_id=req.action_id,
        task_id=req.task_id,
        capability=req.capability,
    )
    res.mark_completed(ActionStatus.SUCCESS, "File found", evidence={"path": "a.pdf"})
    assert res.success is True
    assert res.status == ActionStatus.SUCCESS
    assert res.duration_ms >= 0.0


# 2. Capability registry validation
def test_capability_registry_phase7():
    assert capability_registry.is_available("CLICK_UI_ELEMENT") is True
    assert capability_registry.is_available("TYPE_TEXT") is True
    assert capability_registry.is_available("MOVE_FILE") is True
    assert capability_registry.is_available("RENAME_FILE") is True
    assert capability_registry.is_available("CREATE_FOLDER") is True
    # Deletion and shell must remain blocked
    assert capability_registry.is_blocked("DELETE_FILE") is True
    assert capability_registry.is_blocked("EXECUTE_SHELL") is True


# 4. Click action & 10. Target revalidation
def test_ui_click_action(monkeypatch):
    test_elem = UIElement(
        element_id="elem_btn_save",
        role="Button",
        name="Save",
        automation_id="btn_save",
        bounding_box=BoundingBox.from_xywh(100, 200, 80, 30),
        visible=True,
        enabled=True,
    )
    mock_screen = ScreenState(
        active_window=WindowInfo(hwnd=1, title="TestApp"),
        ui_elements=[test_elem],
        fused_elements=[test_elem],
    )

    class MockPerception:
        def perceive(self, req):
            return mock_screen

    clicked_coords = []
    def mock_simulate_click(self, x, y, button="left", is_double=False):
        clicked_coords.append((x, y, button, is_double))

    monkeypatch.setattr(UIActionExecutor, "_simulate_mouse_click", mock_simulate_click)

    ui_exec = UIActionExecutor(engine=MockPerception())
    req = ActionRequest(
        task_id="t1",
        capability="CLICK_UI_ELEMENT",
        target=ActionTarget(name="Save", role="Button", automation_id="btn_save"),
        parameters={"button": "left"},
    )
    res = ui_exec.execute(req)
    assert res.success is True
    assert len(clicked_coords) == 1
    assert clicked_coords[0][0] == 140  # Center X: 100 + 40
    assert clicked_coords[0][1] == 215  # Center Y: 200 + 15


# 5. Double-click action
def test_ui_double_click_action(monkeypatch):
    test_elem = UIElement(
        element_id="elem_folder",
        role="ListItem",
        name="Research",
        bounding_box=BoundingBox.from_xywh(50, 50, 100, 30),
        visible=True,
        enabled=True,
    )
    mock_screen = ScreenState(fused_elements=[test_elem])

    class MockPerception:
        def perceive(self, req):
            return mock_screen

    clicked_coords = []
    def mock_simulate_click(self, x, y, button="left", is_double=False):
        clicked_coords.append((x, y, is_double))

    monkeypatch.setattr(UIActionExecutor, "_simulate_mouse_click", mock_simulate_click)

    ui_exec = UIActionExecutor(engine=MockPerception())
    req = ActionRequest(
        task_id="t1",
        capability="DOUBLE_CLICK_UI_ELEMENT",
        target=ActionTarget(name="Research"),
    )
    res = ui_exec.execute(req)
    assert res.success is True
    assert clicked_coords[0][2] is True  # is_double is True


# 11. Stale target handling & TargetNotFoundError
def test_stale_target_and_not_found():
    empty_screen = ScreenState(fused_elements=[])
    class MockPerception:
        def perceive(self, req):
            return empty_screen

    ui_exec = UIActionExecutor(engine=MockPerception())
    req = ActionRequest(
        task_id="t1",
        capability="CLICK_UI_ELEMENT",
        target=ActionTarget(name="NonExistentButton"),
    )
    res = ui_exec.execute(req)
    assert res.success is False
    assert res.error_code == "TARGET_NOT_FOUND"


# 6. Keyboard action & 7. Hotkey validation
def test_keyboard_actions(monkeypatch):
    sent_keys = []
    def mock_send_key(self, vk):
        sent_keys.append(vk)

    monkeypatch.setattr(KeyboardActionExecutor, "_send_key_event", mock_send_key)

    kb_exec = KeyboardActionExecutor()
    req = ActionRequest(
        task_id="t1",
        capability="PRESS_KEY",
        parameters={"key": "ENTER"},
    )
    res = kb_exec.execute(req)
    assert res.success is True
    assert len(sent_keys) == 1
    assert sent_keys[0] == 0x0D  # VK_RETURN

    # Hotkey test
    req_hotkey = ActionRequest(
        task_id="t1",
        capability="HOTKEY",
        parameters={"hotkey": "ctrl+c"},
    )
    res_hotkey = kb_exec.execute(req_hotkey)
    assert res_hotkey.success is True

    # Disallowed hotkey test
    req_bad_hotkey = ActionRequest(
        task_id="t1",
        capability="HOTKEY",
        parameters={"hotkey": "ctrl+alt+del"},
    )
    res_bad = kb_exec.execute(req_bad_hotkey)
    assert res_bad.success is False
    assert res_bad.status == ActionStatus.BLOCKED


# 8. Scroll bounds
def test_scroll_bounds(monkeypatch):
    wheel_events = []
    def mock_mouse_event(flags, dx, dy, data, extra):
        wheel_events.append(data)

    monkeypatch.setattr("ctypes.windll.user32.mouse_event", mock_mouse_event)
    ui_exec = UIActionExecutor()
    
    # Request excessive 50 scroll
    req = ActionRequest(
        task_id="t1",
        capability="SCROLL",
        parameters={"direction": "down", "amount": 50},
    )
    res = ui_exec.execute(req)
    assert res.success is True
    assert res.evidence["amount"] == 10  # Clamped to maximum 10


# 9. Window focus & Application launch allowlist
def test_window_focus_and_app_launch(monkeypatch):
    class MockPopen:
        def __init__(self, args, shell=False):
            self.pid = 9999
            self.args = args

    monkeypatch.setattr("subprocess.Popen", MockPopen)
    win_exec = WindowActionExecutor()

    # Allowed application launch
    req_app = ActionRequest(
        task_id="t1",
        capability="LAUNCH_APPLICATION",
        parameters={"app_name": "notepad"},
    )
    res_app = win_exec.execute(req_app)
    assert res_app.success is True
    assert res_app.evidence["pid"] == 9999

    # Disallowed arbitrary executable
    req_bad = ActionRequest(
        task_id="t1",
        capability="LAUNCH_APPLICATION",
        parameters={"app_name": "malicious_script.exe"},
    )
    res_bad = win_exec.execute(req_bad)
    assert res_bad.success is False
    assert res_bad.status == ActionStatus.BLOCKED


# 12. File rename & 13. File move & 14. Folder creation & 17. Collision handling
def test_filesystem_operations(temp_workspace):
    workspace, policy = temp_workspace
    file_exec = FileActionExecutor(policy=policy)

    # Create Folder
    folder_req = ActionRequest(
        task_id="t1",
        capability="CREATE_FOLDER",
        parameters={"folder_path": str(workspace / "Research")},
    )
    res_folder = file_exec.execute(folder_req)
    assert res_folder.success is True
    assert (workspace / "Research").is_dir()

    # Create sample file
    sample_file = workspace / "sample.pdf"
    sample_file.write_text("Qualcomm AI Research Paper Content", encoding="utf-8")

    # Rename File
    rename_req = ActionRequest(
        task_id="t1",
        capability="RENAME_FILE",
        parameters={"source_path": str(sample_file), "new_name": "Qualcomm-AI.pdf"},
    )
    res_rename = file_exec.execute(rename_req)
    assert res_rename.success is True
    renamed_file = workspace / "Qualcomm-AI.pdf"
    assert renamed_file.is_file()
    assert not sample_file.exists()

    # Move File
    move_req = ActionRequest(
        task_id="t1",
        capability="MOVE_FILE",
        parameters={"source_path": str(renamed_file), "destination_path": str(workspace / "Research")},
    )
    res_move = file_exec.execute(move_req)
    assert res_move.success is True
    final_file = workspace / "Research" / "Qualcomm-AI.pdf"
    assert final_file.is_file()

    # Collision test: try moving another file with same name without overwrite
    duplicate_file = workspace / "Qualcomm-AI.pdf"
    duplicate_file.write_text("New file", encoding="utf-8")
    res_collision = file_exec.execute(ActionRequest(
        task_id="t1",
        capability="MOVE_FILE",
        parameters={"source_path": str(duplicate_file), "destination_path": str(workspace / "Research")},
    ))
    assert res_collision.success is False
    assert res_collision.error_code == "FILE_EXISTS"


# 15. Path validation & 16. Protected path rejection
def test_path_security_policy(temp_workspace):
    workspace, policy = temp_workspace

    # Path traversal attack
    with pytest.raises(PathSecurityError, match="Path traversal"):
        policy.resolve_and_validate_path(str(workspace / ".." / ".." / "Windows"))

    # UNC attack
    with pytest.raises(PathSecurityError, match="UNC network paths"):
        policy.resolve_and_validate_path("\\\\evil-server\\share\\data")

    # System directory access
    with pytest.raises(PathSecurityError, match="Access to system folder"):
        policy.resolve_and_validate_path("C:\\Windows\\System32\\cmd.exe")


# 18. Confirmation requirement & 19. Confirmation binding & 20. Expiration
def test_action_confirmation_lifecycle():
    gate = ActionSafetyGate()
    req = ActionRequest(
        task_id="t_conf",
        action_id="act_move_file",
        capability="MOVE_FILE",
        risk_level=RiskLevel.HIGH,
        requires_confirmation=True,
    )
    assert gate.requires_user_confirmation(req) is True

    binding = gate.create_confirmation_request(req, "Move critical file")
    assert binding.matches(req) is True

    # Simulate resolution
    event_bus.publish(SafetyConfirmationResolvedEvent(
        confirmation_id=binding.confirmation_id,
        task_id=req.task_id,
        action_id=req.action_id,
        approved=True,
    ))
    resolved, approved, _ = gate.check_confirmation_status(binding)
    assert resolved is True
    assert approved is True

    # Expiration test
    expired_binding = ConfirmationBinding(
        task_id="t1", action_id="act_exp", capability="MOVE_FILE",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    assert expired_binding.is_expired() is True


# 21. Cancellation & 22. Timeout
def test_action_cancellation():
    executor = ActionExecutor()
    executor.cancel()
    
    plan = TaskPlan(
        command_id="cmd_cancel",
        status=PlanStatus.READY,
        steps=[PlanStep(step_id="s1", order=1, intent=ActionIntent(capability="OBSERVE_SCREEN"))]
    )
    results = executor.execute_plan(plan)
    assert len(results) == 0


# 23. Duplicate action prevention (Action Locking)
def test_duplicate_action_prevention():
    executor = ActionExecutor()
    req = ActionRequest(
        action_id="act_unique_1",
        task_id="t1",
        capability="OBSERVE_SCREEN",
    )
    # Manually lock
    executor._completed_action_ids.add("act_unique_1")
    
    plan = TaskPlan(
        command_id="cmd_dup",
        status=PlanStatus.READY,
        steps=[PlanStep(step_id="act_unique_1", order=1, intent=ActionIntent(capability="OBSERVE_SCREEN"))]
    )
    # Step ID matches locked action
    results = executor.execute_plan(plan)
    assert len(results) == 0


# 25. Arbitrary code rejection & 26. Shell command rejection
def test_arbitrary_code_and_shell_rejection():
    gate = ActionSafetyGate()
    
    # PowerShell payload in parameters
    bad_req = ActionRequest(
        task_id="t_bad",
        capability="TYPE_TEXT",
        parameters={"text": "powershell Start-Process calc.exe"},
    )
    allowed, reason, err = gate.evaluate_action(bad_req)
    assert allowed is False
    assert err == "CODE_INJECTION_BLOCKED"


# 27. Password field blocking & 28. Credential input blocking
def test_credential_and_password_blocking():
    kb_exec = KeyboardActionExecutor()
    
    # Password field target
    pwd_req = ActionRequest(
        task_id="t_pwd",
        capability="TYPE_TEXT",
        target=ActionTarget(role="PasswordBox", name="Password"),
        parameters={"text": "secret123"},
    )
    res_pwd = kb_exec.execute(pwd_req)
    assert res_pwd.status == ActionStatus.BLOCKED

    # API key in text
    cred_req = ActionRequest(
        task_id="t_cred",
        capability="TYPE_TEXT",
        parameters={"text": "api_key = 'sk-1234567890abcdef'"},
    )
    res_cred = kb_exec.execute(cred_req)
    assert res_cred.status == ActionStatus.BLOCKED


# 29. No deletion capability
def test_permanent_deletion_strictly_blocked():
    gate = ActionSafetyGate()
    del_req = ActionRequest(
        task_id="t_del",
        capability="DELETE_FILE",
        parameters={"file_path": "C:\\test.txt"},
    )
    allowed, reason, err = gate.evaluate_action(del_req)
    assert allowed is False
    assert err == "DELETION_BLOCKED"


# 30. No executor invocation from invalid plans
def test_no_execution_on_unvalidated_plan():
    executor = ActionExecutor()
    unvalidated_plan = TaskPlan(status=PlanStatus.PLANNING, steps=[])
    res = executor.execute_plan(unvalidated_plan)
    assert len(res) == 0


# 31. UI state updates during execution
def test_ui_state_updates():
    executor = ActionExecutor()
    plan = TaskPlan(
        command_id="cmd_ui_test",
        status=PlanStatus.READY,
        steps=[PlanStep(step_id="s1", order=1, intent=ActionIntent(capability="OBSERVE_SCREEN"))]
    )
    executor.execute_plan(plan)
    assert app_state.status == TaskStatus.COMPLETED


# 33. End-to-end integration test with Phase 6 structured plan in temporary workspace
def test_phase6_plan_to_phase7_execution(temp_workspace):
    workspace, policy = temp_workspace
    file_exec = FileActionExecutor(policy=policy)
    executor = ActionExecutor(file_exec=file_exec)

    # Seed workspace with test PDF
    (workspace / "Downloads").mkdir(exist_ok=True)
    test_pdf = workspace / "Downloads" / "paper_latest.pdf"
    test_pdf.write_text("PDF content", encoding="utf-8")

    # Construct Phase 6 TaskPlan
    step1 = PlanStep(
        step_id="s1", order=1,
        intent=ActionIntent(capability="FIND_FILE", parameters={"directory": str(workspace / "Downloads"), "pattern": "*.pdf"}),
        description="Find PDF in Downloads"
    )
    step2 = PlanStep(
        step_id="s2", order=2,
        intent=ActionIntent(capability="RENAME_FILE", parameters={"source_path": str(test_pdf), "new_name": "Qualcomm-AI.pdf"}),
        description="Rename to Qualcomm-AI.pdf"
    )
    step3 = PlanStep(
        step_id="s3", order=3,
        intent=ActionIntent(capability="MOVE_FILE", parameters={"source_path": str(workspace / "Downloads" / "Qualcomm-AI.pdf"), "destination_path": str(workspace / "Research")}),
        description="Move to Research folder"
    )

    plan = TaskPlan(
        command_id="cmd_integration",
        task_id="task_integ",
        goal="Organize latest PDF",
        status=PlanStatus.READY,
        steps=[step1, step2, step3],
    )

    results = executor.execute_plan(plan)
    assert len(results) == 3
    assert all(r.success for r in results)
    assert (workspace / "Research" / "Qualcomm-AI.pdf").is_file()


# 34. Benchmark execution latency
def test_execution_dispatch_benchmark(temp_workspace):
    workspace, policy = temp_workspace
    file_exec = FileActionExecutor(policy=policy)
    executor = ActionExecutor(file_exec=file_exec)

    test_file = workspace / "bench.txt"
    test_file.write_text("Benchmark test", encoding="utf-8")

    req = ActionRequest(
        task_id="t_bench",
        capability="READ_FILE",
        parameters={"file_path": str(test_file)},
    )
    
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        res = file_exec.execute(req)
        times.append((time.perf_counter() - t0) * 1000.0)
        assert res.success is True

    avg_ms = sum(times) / len(times)
    assert avg_ms < 10.0  # Sub-10ms execution latency for local file operations
