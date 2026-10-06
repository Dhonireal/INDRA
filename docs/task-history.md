# VisionPilot — Task History & Audit Trail Specification

> Subsystem: Persistent Task History, Relational Audit Trail & Privacy Redaction  
> Database Engine: SQLite (Local-first, zero-cloud)  
> Storage Location: `data/visionpilot.db`  

---

## 1. Overview

VisionPilot implements a real, persistent Task History and Audit Trail system across application sessions. It records user intent, formulated plans, action executions, postcondition verifications, recovery interventions, safety confirmations, and append-only audit events into a normalized SQLite database.

Crucially, the system operates under strict **privacy-first constraints**: all sensitive values (passwords, tokens, API keys, credentials) are sanitized by the `PrivacyRedactor` before reaching SQLite storage.

---

## 2. Database Schema

The database schema consists of six normalized relational tables:

```
┌──────────────┐       1:1       ┌──────────────────┐
│    tasks     │─────────────────│    task_plans    │
└──────────────┘                 └──────────────────┘
       │
       │ 1:N
       ├─────────────────────────┐
       ▼                         ▼
┌──────────────┐         ┌──────────────────┐
│ task_actions │         │  task_recoveries │
└──────────────┘         └──────────────────┘
       │
       ▼ 1:N
┌───────────────────┐    ┌──────────────────┐
│task_verifications │    │   audit_events   │
└───────────────────┘    └──────────────────┘
```

### Table: `tasks`
Central lifecycle registry for each user command and resulting task.
- `task_id` (TEXT, PRIMARY KEY): Unique task identifier (e.g. `task_8f16da331f66`).
- `command_id` (TEXT): Associated command identifier.
- `user_command` (TEXT): Normalized command prompt (sanitized).
- `command_source` (TEXT): Origin of command (`TEXT`, `VOICE`, `API`, `SYSTEM`).
- `status` (TEXT): Lifecycle status (`CREATED`, `PLANNING`, `WAITING_CONFIRMATION`, `EXECUTING`, `VERIFYING`, `RECOVERING`, `COMPLETED`, `PARTIALLY_COMPLETED`, `FAILED`, `UNCERTAIN`, `CANCELLED`, `INTERRUPTED`).
- `created_at` (TEXT): ISO 8601 creation timestamp.
- `started_at` (TEXT, Nullable): ISO 8601 execution start timestamp.
- `completed_at` (TEXT, Nullable): ISO 8601 completion timestamp.
- `duration_ms` (REAL): End-to-end execution duration in milliseconds.
- `final_outcome` (TEXT, Nullable): Human-readable summary of task completion.
- `error_code` (TEXT, Nullable): Categorical error code if failed.
- `error_message_redacted` (TEXT, Nullable): Sanitized error message.
- `cancellation_reason` (TEXT, Nullable): User or timeout cancellation rationale.
- `plan_id` (TEXT, Nullable): Formulated plan identifier.
- `verification_status` (TEXT, Nullable): Verification outcome (`VERIFIED`, `PARTIAL`, `UNCERTAIN`, `FAILED`).
- `recovery_count` (INTEGER): Number of recovery attempts executed.

### Table: `task_plans`
Stores structured metadata for plans formulated by the AI Task Planner.
- `plan_id` (TEXT, PRIMARY KEY): Unique plan identifier.
- `task_id` (TEXT, FOREIGN KEY → `tasks.task_id` ON DELETE CASCADE).
- `provider` (TEXT): Reasoning provider (`local`, `mock`).
- `model` (TEXT): Model identifier (e.g. `VisionPilot-Deterministic-Planner-v1`).
- `number_of_steps` (INTEGER): Total steps in the plan.
- `generated_at` (TEXT): ISO 8601 generation timestamp.
- `planning_duration_ms` (REAL): Planning latency.
- `plan_validation_status` (TEXT): Plan validation state (`VALID`, `REPAIRED`).
- `risk_summary` (TEXT): Highest step risk level (`SAFE`, `LOW`, `MEDIUM`, `HIGH`).
- `goal` (TEXT): High-level goal.
- `summary` (TEXT): Execution summary.
- `steps_json` (TEXT): Safe JSON array of step descriptions and preconditions.

### Table: `task_actions`
Individual capability execution records.
- `action_id` (TEXT, PRIMARY KEY): Unique action identifier.
- `task_id` (TEXT, FOREIGN KEY → `tasks.task_id` ON DELETE CASCADE).
- `step_index` (INTEGER): 0-indexed step order.
- `capability` (TEXT): Executed capability (`MOVE_FILE`, `CLICK_UI_ELEMENT`, etc.).
- `action_type` (TEXT): Action type.
- `target_reference` (TEXT): Target element name or file path.
- `risk_level` (TEXT): Action risk category.
- `confirmation_required` (INTEGER): Boolean flag (1/0).
- `confirmation_status` (TEXT): `APPROVED`, `DENIED`, `EXPIRED`, `NOT_REQUIRED`.
- `started_at` (TEXT, Nullable): Action start timestamp.
- `completed_at` (TEXT, Nullable): Action completion timestamp.
- `duration_ms` (REAL): Action execution time.
- `executor_status` (TEXT): Execution status (`SUCCESS`, `FAILED`, `BLOCKED`, `TIMEOUT`).
- `result_status` (TEXT, Nullable): Categorical result.
- `error_code` (TEXT, Nullable): Action error code.
- `error_message_redacted` (TEXT, Nullable): Sanitized error message.
- `parameters_redacted` (TEXT): JSON parameters with sensitive inputs masked.

### Table: `task_verifications`
Independent postcondition evaluation records.
- `verification_id` (TEXT, PRIMARY KEY): Unique verification identifier.
- `task_id` (TEXT, FOREIGN KEY → `tasks.task_id` ON DELETE CASCADE).
- `action_id` (TEXT, Nullable): Associated action identifier.
- `status` (TEXT): Status (`VERIFIED`, `FAILED`, `UNCERTAIN`, `TIMEOUT`).
- `verified` (INTEGER): Boolean flag (1/0).
- `confidence` (REAL): Confidence score (0.0 to 1.0).
- `strategy` (TEXT): Verifier strategy name (e.g. `FileMovedVerifier`).
- `expected_state_summary` (TEXT): Description of expected postcondition.
- `actual_state_summary` (TEXT): Observed evidence from UIA, filesystem, or OCR.
- `mismatch_summary` (TEXT, Nullable): Reason for failure if mismatched.
- `recovery_recommended` (INTEGER): Boolean flag (1/0).
- `created_at` (TEXT): Verification timestamp.
- `duration_ms` (REAL): Verification latency.

### Table: `task_recoveries`
Records of recovery interventions evaluated by `RecoveryManager`.
- `recovery_id` (TEXT, PRIMARY KEY): Unique recovery identifier.
- `task_id` (TEXT, FOREIGN KEY → `tasks.task_id` ON DELETE CASCADE).
- `action_id` (TEXT, Nullable): Associated action identifier.
- `recovery_depth` (INTEGER): Current attempt number (capped at 3).
- `decision` (TEXT): Strategy (`RETRY`, `REPERCEIVE`, `REPLAN`, `ASK_USER`, `ABORT`).
- `reason` (TEXT): Rationale for recovery decision.
- `outcome` (TEXT, Nullable): Recovery outcome (`SUCCESS`, `FAILED`).
- `created_at` (TEXT): Recovery timestamp.
- `duration_ms` (REAL): Recovery evaluation latency.

### Table: `audit_events`
Append-only immutable audit trail.
- `event_id` (TEXT, PRIMARY KEY): Unique event identifier (`audit_...`).
- `task_id` (TEXT): Associated task identifier.
- `event_type` (TEXT): Event category (e.g. `COMMAND_RECEIVED`, `TASK_CREATED`, `PLAN_CREATED`, `CONFIRMATION_REQUESTED`, `ACTION_STARTED`, `VERIFICATION_COMPLETED`, `TASK_COMPLETED`).
- `timestamp` (TEXT): ISO 8601 event timestamp.
- `severity` (TEXT): `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- `metadata_json` (TEXT): Structured context dictionary.
- `message_redacted` (TEXT): Sanitized human-readable event description.

---

## 3. Privacy & Redaction Engine

The `PrivacyRedactor` class protects user privacy prior to database persistence:
1. **API Keys & Tokens**: Redacts OpenAI keys (`sk-...`), Google API keys (`AIza...`), GitHub tokens (`ghp_...`, `github_pat_...`), Bearer tokens, and hex hashes exceeding 32 characters.
2. **Password & Credential Inputs**: When action capabilities (`TYPE_TEXT`, `SET_VALUE`, `FILL_FORM`) target fields with names containing `password`, `pwd`, `pin`, `secret`, `token`, `ssn`, or `cvv`, parameter values are replaced with `<redacted:password>`.
3. **Dictionary & JSON Sanitization**: Recursively traverses data dictionaries to mask sensitive keys before serialization.
4. **Error Message Scrubbing**: Sanitizes file paths, auth headers, and stack fragments in error messages.

---

## 4. Startup Crash Recovery

If VisionPilot crashes or is terminated abruptly during task execution, tasks may be left in non-terminal states (`PLANNING`, `WAITING_CONFIRMATION`, `EXECUTING`, `VERIFYING`, `RECOVERING`).

On the subsequent application startup, `TaskHistoryService.recover_interrupted_tasks()`:
1. Scans the SQLite database for orphaned non-terminal task records.
2. Transitions their status to `INTERRUPTED`.
3. Sets `cancellation_reason` to `"Execution was interrupted by application shutdown or crash. Not resumed automatically."`.
4. Appends a `TASK_INTERRUPTED` record to `audit_events`.
5. **Strict Safety Guarantee**: Never resumes side-effecting actions automatically.

---

## 5. Retention Policies & History Clearing

### Age-Based Retention
Tasks older than `config.history.retention_days` (default 30 days) are pruned automatically. Tasks currently executing or in non-terminal states are never pruned. Setting `retention_days = 0` retains records indefinitely.

### Volume-Based Retention
The total number of stored tasks is capped at `config.history.max_tasks` (default 1000 tasks). When exceeded, the oldest completed tasks are pruned to respect local storage constraints.

### User-Initiated Clear History
The UI provides an explicit "Clear History" button:
- Prompts user with a confirmation modal explaining that all local history, plans, actions, and audit logs will be deleted.
- Guarantees application configuration and personal files remain untouched.
- Executes within an isolated SQL transaction.
