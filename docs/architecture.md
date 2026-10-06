# VisionPilot — System Architecture

## 1. Architecture Goal

VisionPilot follows a modular agent architecture:

Listen → See → Understand → Plan → Act → Verify

The system must keep perception, reasoning, execution, and verification separated.

---

# 2. High-Level Architecture

                    ┌─────────────────────┐
                    │       USER          │
                    └──────────┬──────────┘
                               │
                       Voice / Text
                               │
                               ▼
                    ┌─────────────────────┐
                    │  INPUT PROCESSOR    │
                    │ STT + Text Handler  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ COMMAND UNDERSTANDER│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    TASK PLANNER     │
                    └──────────┬──────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │        PERCEPTION ENGINE       │
              │                                │
              │ Screen Capture                 │
              │ OCR                            │
              │ Vision                         │
              │ UI Accessibility Information   │
              └────────────────┬───────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  ACTION PLANNER     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    SAFETY ENGINE    │
                    └──────────┬──────────┘
                               │
                       Confirmation?
                         /          \
                       YES          NO
                        │            │
                        └─────┬──────┘
                              ▼
                    ┌─────────────────────┐
                    │   ACTION EXECUTOR   │
                    │ Mouse / Keyboard    │
                    │ Windows Automation  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ VERIFICATION ENGINE │
                    └──────────┬──────────┘
                               │
                         ┌─────┴─────┐
                         │           │
                       SUCCESS      FAIL
                         │           │
                         ▼           ▼
                      RESULT      RECOVERY

---

## 3. Implemented Text Command Pipeline (Phase 3)

The text command pipeline prepares user natural-language commands for the AI task planner:

`	ext
User Text Input (QTextEdit)
      │
      ▼
CommandInputWidget (_handle_submit)
      │ Emits CommandSubmittedEvent
      ▼
CommandService (process_command)
      │
      ├── 1. Validation (CommandValidator)
      │      • Checks min/max length
      │      • Rejects empty/whitespace strings
      │      • Emits CommandValidatedEvent or CommandRejectedEvent
      │
      ├── 2. Normalization (CommandNormalizer)
      │      • NFKC Unicode normalization
      │      • CRLF line ending cleanup
      │      • Horizontal whitespace collapsing
      │      • Emits CommandNormalizedEvent
      │
      ├── 3. Contextualization (CommandContextBuilder)
      │      • Attaches OS, machine, runtime, and app telemetry
      │      • Safe metadata only (no screen capture / file access)
      │
      ├── 4. Structured Task Generation
      │      • Creates CommandRequest (domain model)
      │      • Produces TaskRequest (contract for Phase 6 planner)
      │      • Emits CommandReadyEvent & TaskCreatedEvent
      │
      ├── 5. Application State & UI Update
      │      • Updates AppState status to ANALYZING / READY_FOR_PLANNING
      │      • TaskPanel displays prompt and ready state
      │      • ActivityPanel records new item
      │
      └── 6. Persistence (CommandRepository)
             • Writes command record to SQLite command_history table
```

---

## 4. Implemented AI Task Planner Architecture (Phase 6)

The AI Task Planner operates as a reasoning and structuring layer converting user intent and screen perception into a validated, machine-readable `TaskPlan`:

```text
CommandRequest (Phase 3)
      +
ScreenState (Phase 5: Fused UIA Controls + Untrusted OCR Regions)
      +
CapabilityRegistry (Authorized System Capabilities)
      ↓
PlannerContextManager
      │
      ├── Enforces Trust Boundaries:
      │     • USER_COMMAND (Intent)
      │     • SCREEN_OBSERVATION (Tagged strictly as UNTRUSTED evidence)
      │     • SYSTEM_POLICY (Safety rules and operational limits)
      │     • CAPABILITY_REGISTRY (System authorized capabilities)
      │
      ├── Perception Context Reduction:
      │     • Filters background windows
      │     • Redacts password / sensitive fields
      │
      ▼
ReasoningProvider (LocalReasoningProvider)
      │
      ├── Ambiguity Detection:
      │     • Vague commands trigger clarification requests with candidate options
      │
      ├── Visual Grounding & Target Resolution:
      │     • Prefers stable UIA accessibility attributes (automation_id, role, name)
      │     • Falls back to OCR bounding box coordinates with lower confidence tier
      │
      ├── Dependency Graph Sequencing:
      │     • Maps step preconditions and depends_on step IDs
      │
      ▼
Raw Structured Plan
      ↓
PlanValidator
      │
      ├── 1. Schema Validation (Required fields, order continuity)
      ├── 2. Capability Validation (Only registered capabilities permitted)
      ├── 3. Code Injection Defense (Rejects powershell, cmd, eval, os.system, subprocess)
      ├── 4. Pure Data Verification (Parameters must be structured dictionaries, never code)
      │
      ▼ (If invalid: Bounded 1-Attempt Plan Repair)
Validated TaskPlan
      │
      ├── AppState (Updates plan steps & status to READY)
      ├── EventBus (Emits PlanGeneratedEvent or PlanClarificationRequiredEvent)
      └── TaskPanel (Renders structured Plan Preview with risk badges)

CRITICAL BOUNDARY: The Task Planner is strictly a PLANNER, NOT an executor.
Zero mouse movements, clicks, typing, or filesystem modifications occur here.
```

---

## 5. Implemented Controlled Action Executor Architecture (Phase 7)

The Action Executor serves as VisionPilot's "hands", translating validated `TaskPlan` objects into bounded, observable, and safe computer actions:

```text
Validated TaskPlan (Phase 6)
       │
       ▼
ActionExecutor (execute_plan)
       │
       ├── Sequential Execution Loop (Step-by-step)
       │
       ▼
ActionSafetyGate (Pre-execution validation)
       │
       ├── 1. Schema Validation (ActionRequest structure)
       ├── 2. Capability Validation (Matches registered, active capability)
       ├── 3. Code Injection Detection (Blocks powershell, cmd, eval, os.system, subprocess)
       ├── 4. Permanent Deletion Blocking (DELETE_FILE / DELETE_FOLDER permanently blocked)
       ├── 5. Password / Sensitive Field Blocking (Blocks typing into password controls)
       ├── 6. Credential Pattern Blocking (Blocks API keys, private keys, passwords)
       ├── 7. Confirmation Gate (Evaluates RiskLevel; binds confirmation to task/action/capability)
       │
       ▼ (If all gates pass)
Specialized Capability Executors:
       │
       ├── UIActionExecutor
       │     • Revalidates target in live UI before execution (StaleTargetError protection)
       │     • CLICK_UI_ELEMENT / DOUBLE_CLICK_UI_ELEMENT via UIA or Win32 mouse_event
       │     • SCROLL (strictly bounded 1-10 units)
       │     • OBSERVE_SCREEN
       │
       ├── KeyboardActionExecutor
       │     • TYPE_TEXT (Unicode keybd_event / SendInput simulation)
       │     • PRESS_KEY (Virtual Key allowlist: ENTER, ESC, TAB, BACKSPACE, ARROWS)
       │     • HOTKEY (Strict allowlist: ctrl+c/v/s/a/z/f, alt+tab)
       │
       ├── WindowActionExecutor
       │     • FOCUS_WINDOW (Win32 SetForegroundWindow)
       │     • LAUNCH_APPLICATION (Strict allowlist: notepad, calculator, explorer, settings)
       │
       └── FileActionExecutor (Conscious user-space policy)
             • PathSecurityPolicy: Confines operations to Downloads, Documents, Desktop, Research, and safe test workspaces
             • Blocks traversal (..), UNC paths, root drives, Windows, System32, Program Files, AppData
             • FIND_FILE, READ_FILE (bounded 64KB)
             • CREATE_FOLDER (non-destructive)
             • RENAME_FILE / MOVE_FILE (file collision detection; no overwrite)
             • DELETE_FILE is strictly BLOCKED
       │
       ▼
ActionResult (PENDING, RUNNING, SUCCESS, FAILED, CANCELLED, TIMEOUT, BLOCKED, REQUIRES_CONFIRMATION)
       │
       ├── Action History Logging (Structured audit trail)
       ├── Duplicate Execution Locking (Prevents double clicks or model retry bugs)
       ├── EventBus (Emits ActionRequestedEvent, ActionExecutedEvent, ActionBlockedEvent)
       └── UI Feedback (TaskPanel progress 1/N, real-time status, ActivityPanel record)
```

---

## 6. Implemented Verification & Recovery Engine Architecture (Phase 8)

The Verification & Recovery Engine closes the loop between action execution and true system state:

```text
Action Execution
       │
       ▼
ActionResult (Status, Duration, Initial Evidence)
       +
ExpectedResult (Inferred or Declared Postconditions)
       │
       ▼
VerificationEngine (verify_action)
       │
       ├── Bounded Temporal Polling (100ms intervals up to timeout)
       │
       ├── Strategy Dispatch via VerificationStrategyRegistry:
       │     • FileExistsVerifier / FileAbsentVerifier
       │     • FileMovedVerifier / FileRenamedVerifier (PathSecurityPolicy enforced)
       │     • UIElementPresentVerifier / UIElementAbsentVerifier (UIA tree)
       │     • TextPresentVerifier / TextAbsentVerifier (OCR & UIA text)
       │     • WindowActiveVerifier (SetForegroundWindow / Win32 focus)
       │     • ValueChangedVerifier (Control value comparisons)
       │     • StructuredStateVerifier (Exploratory actions)
       │
       ▼
VerificationResult (VERIFIED, FAILED, UNCERTAIN, TIMEOUT, Evidence, Confidence)
       │
       ├── If VERIFIED -> Proceed to next step
       │
       └── If FAILED or UNCERTAIN -> RecoveryManager (evaluate_failure)
             │
             ├── Strict Policies:
             │     • MAX_RECOVERY_DEPTH = 3 (Infinite loop prevention)
             │     • Blind retries prohibited for side-effecting actions
             │     • File collision -> Escalates to ASK_USER
             │     • UI missing target -> Re-perception before retry
             │     • Untrusted OCR text -> Never converted into recovery commands
             │
             ▼
       RecoveryDecision (RETRY, REPERCEIVE, REPLAN, ASK_USER, ABORT, MARK_FAILED)
             │
             ├── If RETRY / REPERCEIVE: Re-dispatch under SafetyGate
             └── If ASK_USER / ABORT: Halt execution cleanly
       │
       ▼
TaskVerifier (evaluate_task_plan)
       │
       ├── VERIFIED_SUCCESS: 100% of required steps verified
       ├── PARTIALLY_COMPLETED: Non-fatal stop with partial completed steps
       ├── UNCERTAIN: Postconditions could not be conclusively determined
       └── FAILED: Action or verification failed unrecoverably
       │
       ▼
AppState & UI Update (VERIFYING, RECOVERING, PARTIALLY_COMPLETED, UNCERTAIN, COMPLETED)
```

---

## 7. Task History & Audit Trail Engine Architecture (Phase 9)

```
UI Layer (ActivityPanel, TaskDetailDialog, TaskHistoryDialog, SettingsWindow)
       │
       ▼ Queries / Filters / Detail Inspections
TaskHistoryService (Central Orchestrator)
       │
       ├── Subscribes to Decoupled EventBus:
       │     • CommandReceivedEvent
       │     • TaskCreatedEvent / TaskStatusChangedEvent
       │     • PlanGeneratedEvent
       │     • SafetyConfirmationRequiredEvent / SafetyConfirmationResolvedEvent
       │     • ActionRequestedEvent / ActionExecutedEvent / ActionBlockedEvent
       │     • VerificationStartedEvent / VerificationCompletedEvent
       │     • RecoveryDecisionEvent / RecoveryAttemptedEvent
       │     • TaskCompletedEvent / TaskFailedEvent / TaskCancelledEvent
       │
       ├── Startup Crash Recovery (recover_interrupted_tasks):
       │     • Detects orphaned non-terminal tasks from abnormal shutdowns
       │     • Marks state as INTERRUPTED (Never resumes actions automatically)
       │     • Emits TASK_INTERRUPTED audit record
       │
       ├── Privacy & Redaction Layer (PrivacyRedactor):
       │     • Strips API keys, Bearer tokens, GitHub/Google credentials
       │     • Masks password typing inputs (<redacted:password>)
       │     • Sanitizes stack fragments and error messages
       │
       ├── Retention Engine (cleanup_retention):
       │     • Enforces retention_days (default 30 days)
       │     • Enforces max_tasks ceiling (default 1000 tasks)
       │
       ▼
Typed Repository Layer (repositories.py)
       │
       ├── TaskRepository (tasks table)
       ├── TaskPlanRepository (task_plans table)
       ├── ActionRepository (task_actions table)
       ├── VerificationRepository (task_verifications table)
       ├── RecoveryRepository (task_recoveries table)
       └── AuditRepository (audit_events table)
       │
       ▼ Transactional, Parameterized SQL with Foreign Keys
SQLite Storage Layer (data/visionpilot.db)
```


