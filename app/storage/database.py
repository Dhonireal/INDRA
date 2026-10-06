"""
VisionPilot SQLite Database Storage Foundation.

Provides lightweight, local-only SQLite persistence for command history,
task lifecycle records, plan metadata, action outcomes, verification postconditions,
recovery events, and audit trails using Python's standard library sqlite3.
Zero external dependencies.
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
from app.core.config import config
from app.core.logger import logger


def init_db(db_path: Path = config.db_path) -> None:
    """Initializes SQLite tables and indexes if they do not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()

        # 1. Existing command history table (Phase 1-3 compatibility)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                command_id TEXT PRIMARY KEY,
                task_id TEXT,
                raw_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT
            )
        """)

        # 2. Tasks table (Phase 9 central task lifecycle)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                command_id TEXT,
                user_command TEXT NOT NULL,
                command_source TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                duration_ms REAL DEFAULT 0.0,
                final_outcome TEXT,
                error_code TEXT,
                error_message_redacted TEXT,
                cancellation_reason TEXT,
                plan_id TEXT,
                verification_status TEXT,
                recovery_count INTEGER DEFAULT 0
            )
        """)

        # 3. Task Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_plans (
                plan_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                number_of_steps INTEGER DEFAULT 0,
                generated_at TEXT NOT NULL,
                planning_duration_ms REAL DEFAULT 0.0,
                plan_validation_status TEXT NOT NULL,
                risk_summary TEXT,
                goal TEXT,
                summary TEXT,
                steps_json TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            )
        """)

        # 4. Task Actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_actions (
                action_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                capability TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target_reference TEXT,
                risk_level TEXT NOT NULL,
                confirmation_required INTEGER DEFAULT 0,
                confirmation_status TEXT,
                started_at TEXT,
                completed_at TEXT,
                duration_ms REAL DEFAULT 0.0,
                executor_status TEXT NOT NULL,
                result_status TEXT,
                error_code TEXT,
                error_message_redacted TEXT,
                parameters_redacted TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            )
        """)

        # 5. Task Verifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_verifications (
                verification_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                action_id TEXT,
                status TEXT NOT NULL,
                verified INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                strategy TEXT NOT NULL,
                expected_state_summary TEXT,
                actual_state_summary TEXT,
                mismatch_summary TEXT,
                recovery_recommended INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                duration_ms REAL DEFAULT 0.0,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            )
        """)

        # 6. Task Recoveries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_recoveries (
                recovery_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                action_id TEXT,
                recovery_depth INTEGER NOT NULL,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                outcome TEXT,
                created_at TEXT NOT NULL,
                duration_ms REAL DEFAULT 0.0,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
            )
        """)

        # 7. Audit Events table (Append-only)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                severity TEXT NOT NULL,
                metadata_json TEXT,
                message_redacted TEXT
            )
        """)

        # Indexes for fast querying, filtering, and joining
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_command_source ON tasks(command_source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_task_id ON task_plans(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_task_id ON task_actions(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_verifications_task_id ON task_verifications(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recoveries_task_id ON task_recoveries(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_task_id ON audit_events(task_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp)")

        conn.commit()
    logger.debug(f"Database initialized with task and audit schemas at {db_path}")


@contextmanager
def get_db(db_path: Path = config.db_path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager yielding an open SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
