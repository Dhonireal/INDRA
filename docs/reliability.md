# System Reliability & Fault Tolerance — VisionPilot

## 1. Reliability Architecture

VisionPilot achieves enterprise-grade desktop reliability through five architectural pillars:
1. **Independent State Verification:** An action executor return code is never treated as a verification of success.
2. **Deterministic Recovery Engine:** Automated recovery loops with bounded retry depths.
3. **Crash & Interruption Safety:** Process crash recovery that safely preserves history without auto-resuming side-effecting operations.
4. **Asynchronous UI Thread Isolation:** Long-running tasks, OCR, and reasoning execute on background worker threads, preventing GUI freezes.
5. **Database WAL Persistence:** SQLite write-ahead logging (WAL) prevents database corruption on unexpected termination.

---

## 2. Independent State Verification

Execution success does not imply real-world goal achievement.
The `VerificationEngine` operates via specialized verifiers:
- `FileExistsVerifier`: Queries OS filesystem for actual existence and non-zero size.
- `FileAbsentVerifier`: Confirms the original source file has been removed after a move.
- `UIElementPresentVerifier`: Inspects active UIA window tree for target control state.
- `UIElementAbsentVerifier`: Confirms modal dialogs or buttons have closed/disappeared.
- `WindowActiveVerifier`: Validates window handle focus and title.

### Discrepancy Matrix
| Executor Status | Verifier Status | Final Task Result |
|:---:|:---:|:---:|
| Success | Verified | `VERIFIED` |
| Success | Discrepancy / Absent | `FAILED` or `UNCERTAIN` |
| Failure | State Actually Changed | Evaluated by Verifier |
| Timeout | Verified | `VERIFIED` |
| Timeout | Absent / Unreachable | `UNCERTAIN` / `TIMEOUT` |

---

## 3. Recovery Engine & Depth Bounding

When a verification step reports `FAILED` or `UNCERTAIN`:
1. `RecoveryPolicy` determines the appropriate recovery action:
   - `REPERCEIVE`: Re-captures screen state to account for animation or disk IO delays.
   - `RETRY`: Re-attempts an idempotent action.
   - `REPLAN`: Requests a revised decomposition from the planner.
   - `ASK_USER`: Prompts the user when ambiguity cannot be resolved autonomously.
   - `ABORT`: Terminates task execution safely.
2. **Maximum Recovery Depth:**
   - Recovery depth is strictly bounded (default: `max_depth = 2`).
   - If recovery attempts exceed the limit without establishing verification, the task is terminated with `ABORT` and marked `FAILED`. Infinite recovery loops are impossible.
3. **Safety Re-evaluation:**
   - Any recovery action must re-enter `PlanValidator`, `ActionSafetyGate`, and `ConfirmationManager`. Recovery can never bypass safety policies.

---

## 4. Crash Recovery & Startup Safety

If VisionPilot crashes, the OS restarts, or power is lost during task execution:
1. SQLite transactions are committed with Write-Ahead Logging (`PRAGMA journal_mode=WAL`), preventing database corruption.
2. On the next application startup, `TaskRepository` inspects all tasks with unfinalized statuses (`IN_PROGRESS`, `EXECUTING`, `VERIFYING`, `RECOVERING`).
3. These tasks are automatically updated to `INTERRUPTED` or `UNCERTAIN`.
4. **Critical Safety Invariant:** VisionPilot **never** resumes execution of side-effecting actions automatically upon restart. Tasks must be explicitly initiated anew by the user.

---

## 5. UI Thread Isolation & Responsiveness

All non-UI workloads are dispatched via PySide6 `QThread` and `QRunnable` workers:
- Voice transcription workers
- Perception & OCR workers
- Planning & reasoning engine workers
- Verification workers
- Database batch queries

The main Qt event loop remains responsive at all times, handling window resizing, status updates, and user cancellation signals instantaneously.
