"""
VisionPilot Filesystem Verification Strategies.

Implements deterministic postcondition verification for filesystem operations:
- FileExistsVerifier (verifies existence, type, and accessibility)
- FileAbsentVerifier (verifies path absence)
- FileRenamedVerifier (verifies new path exists and old path is absent)
- FileMovedVerifier (verifies destination exists, source absent, checks collisions)

CRITICAL SAFETY:
- Uses pure Python pathlib and os.stat APIs (never shell/cmd commands).
- Integrates PathSecurityPolicy to enforce permitted user directory confinement.
- Normalizes Windows path separators and casing.
- Collects structured evidence without loading large file payloads into memory.
"""
import os
from pathlib import Path
import time
from typing import Any, Dict, Optional

from app.core.exceptions import PathSecurityError
from app.core.logger import logger
from app.execution.path_policy import PathSecurityPolicy
from app.execution.schema import ActionResult, ActionStatus
from app.verification.schema import (
    ExpectedResult, ExpectedResultType, VerificationConfidence,
    VerificationResult, VerificationStatus
)
from app.verification.strategies.base import VerificationStrategy


def _normalize_path(raw_path: str, policy: Optional[PathSecurityPolicy] = None) -> Path:
    """Normalizes and safely resolves a Windows path according to policy."""
    if policy:
        return policy.resolve_and_validate_path(raw_path, must_exist=False, operation_name="verify_file")
    p = Path(raw_path).resolve()
    return p


class FileExistsVerifier(VerificationStrategy):
    """Verifies that an expected file or directory exists and is accessible."""

    def __init__(self, policy: Optional[PathSecurityPolicy] = None) -> None:
        self.policy = policy or PathSecurityPolicy()

    @property
    def strategy_name(self) -> str:
        return "FileExistsVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.FILE_EXISTS

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"path": expected.target, "type": expected.expected_value or "any"}
        )

        try:
            target_path = _normalize_path(expected.target, self.policy)
        except PathSecurityError as e:
            res.mark_failed(self.strategy_name, f"Security violation: {e}", recommend_recovery=False)
            return res

        if not target_path.exists():
            res.actual_state = {"exists": False, "path": str(target_path)}
            res.mark_failed(
                self.strategy_name,
                f"Expected path does not exist: {target_path}",
                evidence={"path": str(target_path), "exists": False}
            )
            return res

        # Check type (file vs directory) if requested
        must_be_dir = expected.parameters.get("must_be_directory", False) or expected.expected_value == "directory"
        must_be_file = expected.parameters.get("must_be_file", False) or expected.expected_value == "file"

        try:
            stat_info = target_path.stat()
            is_dir = target_path.is_dir()
            is_file = target_path.is_file()

            evidence = {
                "path": str(target_path),
                "exists": True,
                "is_directory": is_dir,
                "is_file": is_file,
                "size_bytes": stat_info.st_size,
                "mtime": stat_info.st_mtime,
            }
            res.actual_state = evidence

            if must_be_dir and not is_dir:
                res.mark_failed(self.strategy_name, f"Expected directory but found file: {target_path}", evidence=evidence)
                return res

            if must_be_file and not is_file:
                res.mark_failed(self.strategy_name, f"Expected file but found directory: {target_path}", evidence=evidence)
                return res

            res.mark_verified(self.strategy_name, VerificationConfidence.STRONG, evidence=evidence)
            return res

        except Exception as ex:
            res.mark_failed(self.strategy_name, f"Filesystem stat error: {ex}", evidence={"error": str(ex)})
            return res


class FileAbsentVerifier(VerificationStrategy):
    """Verifies that a specified path does NOT exist."""

    def __init__(self, policy: Optional[PathSecurityPolicy] = None) -> None:
        self.policy = policy or PathSecurityPolicy()

    @property
    def strategy_name(self) -> str:
        return "FileAbsentVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.FILE_ABSENT

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"path": expected.target, "should_exist": False}
        )

        try:
            target_path = _normalize_path(expected.target, self.policy)
        except PathSecurityError as e:
            res.mark_failed(self.strategy_name, f"Security violation: {e}", recommend_recovery=False)
            return res

        exists = target_path.exists()
        res.actual_state = {"exists": exists, "path": str(target_path)}

        if exists:
            res.mark_failed(
                self.strategy_name,
                f"Path was expected to be absent, but still exists: {target_path}",
                evidence={"path": str(target_path), "exists": True}
            )
        else:
            res.mark_verified(
                self.strategy_name,
                VerificationConfidence.STRONG,
                evidence={"path": str(target_path), "exists": False}
            )

        return res


class FileRenamedVerifier(VerificationStrategy):
    """Verifies that a file was successfully renamed: new path exists and old path is absent."""

    def __init__(self, policy: Optional[PathSecurityPolicy] = None) -> None:
        self.policy = policy or PathSecurityPolicy()

    @property
    def strategy_name(self) -> str:
        return "FileRenamedVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.FILE_RENAMED

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"new_target": expected.target, "old_source": expected.secondary_target}
        )

        src_raw = expected.secondary_target or expected.parameters.get("source_path", "")
        dest_raw = expected.target

        try:
            src_path = _normalize_path(src_raw, self.policy)
            if "/" not in dest_raw and "\\" not in dest_raw:
                dest_path = src_path.parent / dest_raw
                dest_path = _normalize_path(str(dest_path), self.policy)
            else:
                dest_path = _normalize_path(dest_raw, self.policy)
        except PathSecurityError as e:
            res.mark_failed(self.strategy_name, f"Security violation: {e}", recommend_recovery=False)
            return res

        src_exists = src_path.exists()
        dest_exists = dest_path.exists()

        evidence = {
            "source_path": str(src_path),
            "source_exists": src_exists,
            "destination_path": str(dest_path),
            "destination_exists": dest_exists,
        }
        res.actual_state = evidence

        # Postcondition: Destination MUST exist, and Source MUST be absent
        if dest_exists and not src_exists:
            dest_stat = dest_path.stat()
            evidence["size_bytes"] = dest_stat.st_size
            evidence["mtime"] = dest_stat.st_mtime
            res.mark_verified(self.strategy_name, VerificationConfidence.STRONG, evidence=evidence)
        elif not dest_exists and src_exists:
            res.mark_failed(
                self.strategy_name,
                f"File was not renamed: destination does not exist and source remains at {src_path}.",
                evidence=evidence
            )
        elif dest_exists and src_exists:
            # File collision or duplicate
            res.mark_uncertain(
                self.strategy_name,
                f"Uncertain state: both original file ({src_path}) and renamed file ({dest_path}) exist.",
                evidence=evidence
            )
        else:
            res.mark_failed(
                self.strategy_name,
                f"File missing: neither original ({src_path}) nor destination ({dest_path}) exists.",
                evidence=evidence
            )

        return res


class FileMovedVerifier(VerificationStrategy):
    """Verifies that a file was successfully moved: destination exists and source is absent."""

    def __init__(self, policy: Optional[PathSecurityPolicy] = None) -> None:
        self.policy = policy or PathSecurityPolicy()

    @property
    def strategy_name(self) -> str:
        return "FileMovedVerifier"

    def can_verify(self, expected_type: ExpectedResultType) -> bool:
        return expected_type == ExpectedResultType.FILE_MOVED

    def verify(
        self,
        action_result: ActionResult,
        expected: ExpectedResult,
        before_state: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        res = VerificationResult(
            task_id=action_result.task_id,
            action_id=action_result.action_id,
            strategy=self.strategy_name,
            expected_state={"destination": expected.target, "source": expected.secondary_target}
        )

        src_raw = expected.secondary_target or expected.parameters.get("source_path", "")
        dest_raw = expected.target

        try:
            src_path = _normalize_path(src_raw, self.policy)
            dest_path = _normalize_path(dest_raw, self.policy)
        except PathSecurityError as e:
            res.mark_failed(self.strategy_name, f"Security violation: {e}", recommend_recovery=False)
            return res

        # If dest_path is a directory, the target moved file has the same name as src_path
        if dest_path.is_dir():
            dest_file_path = dest_path / src_path.name
        else:
            dest_file_path = dest_path

        src_exists = src_path.exists()
        dest_exists = dest_file_path.exists()

        evidence = {
            "source_path": str(src_path),
            "source_exists": src_exists,
            "destination_path": str(dest_file_path),
            "destination_exists": dest_exists,
        }
        res.actual_state = evidence

        # Postcondition: Destination exists AND Source is absent
        if dest_exists and not src_exists:
            dest_stat = dest_file_path.stat()
            evidence["size_bytes"] = dest_stat.st_size
            evidence["mtime"] = dest_stat.st_mtime

            # If before_state had source size, verify size match
            if isinstance(before_state, dict) and "size_bytes" in before_state:
                expected_size = before_state["size_bytes"]
                if dest_stat.st_size != expected_size:
                    res.mark_uncertain(
                        self.strategy_name,
                        f"Destination size ({dest_stat.st_size} bytes) does not match source size ({expected_size} bytes).",
                        evidence=evidence
                    )
                    return res

            res.mark_verified(self.strategy_name, VerificationConfidence.STRONG, evidence=evidence)
        elif not dest_exists and src_exists:
            res.mark_failed(
                self.strategy_name,
                f"File was not moved: destination does not exist and source remains at {src_path}.",
                evidence=evidence
            )
        elif dest_exists and src_exists:
            res.mark_uncertain(
                self.strategy_name,
                f"Collision or partial copy: both source ({src_path}) and destination ({dest_file_path}) exist.",
                evidence=evidence
            )
        else:
            res.mark_failed(
                self.strategy_name,
                f"File missing: neither source ({src_path}) nor destination ({dest_file_path}) exists.",
                evidence=evidence
            )

        return res
