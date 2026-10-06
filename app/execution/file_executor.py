"""
VisionPilot Filesystem Action Executor.

Implements safe, bounded filesystem capabilities:
- FIND_FILE: Search for matching file by extension/pattern in user folder
- READ_FILE: Read text content/metadata bounded by max_bytes
- CREATE_FOLDER: Create user directory if policy allows
- RENAME_FILE: Rename file within authorized user directory
- MOVE_FILE: Move file from source to destination directory

STRICT BOUNDARY:
- Permanent file deletion (DELETE_FILE, format, rmdir) is BLOCKED.
- Uses standard Python pathlib and shutil (ZERO shell or subprocess calls).
- Prevents silent overwrites / file collisions.
"""
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional

from app.core.exceptions import (
    ExecutionError, FileCollisionError, PathSecurityError
)
from app.core.logger import logger
from app.execution.path_policy import PathSecurityPolicy, path_security_policy
from app.execution.schema import ActionRequest, ActionResult, ActionStatus


class FileActionExecutor:
    """Executes validated, safe filesystem operations."""

    def __init__(self, policy: Optional[PathSecurityPolicy] = None) -> None:
        self.policy = policy or path_security_policy

    def execute(self, request: ActionRequest) -> ActionResult:
        """Dispatches filesystem action based on capability."""
        result = ActionResult(
            action_id=request.action_id,
            task_id=request.task_id,
            capability=request.capability,
            target_description=request.target.name or "file",
        )

        cap = request.capability
        try:
            if cap == "FIND_FILE":
                return self._execute_find_file(request, result)
            elif cap == "READ_FILE":
                return self._execute_read_file(request, result)
            elif cap == "CREATE_FOLDER":
                return self._execute_create_folder(request, result)
            elif cap == "RENAME_FILE":
                return self._execute_rename_file(request, result)
            elif cap == "MOVE_FILE":
                return self._execute_move_file(request, result)
            elif cap == "DELETE_FILE":
                result.mark_completed(
                    ActionStatus.BLOCKED,
                    "Permanent file deletion is strictly BLOCKED by policy.",
                    error_code="OPERATION_BLOCKED"
                )
                return result
            else:
                result.mark_completed(
                    ActionStatus.FAILED,
                    f"Unsupported filesystem capability '{cap}'.",
                    error_code="UNSUPPORTED_CAPABILITY"
                )
                return result
        except PathSecurityError as e:
            logger.warning(f"File security policy rejected action [{request.action_id}]: {e.message}")
            result.mark_completed(ActionStatus.BLOCKED, e.message, error_code="SECURITY_VIOLATION")
            return result
        except FileCollisionError as e:
            logger.warning(f"File collision during action [{request.action_id}]: {e.message}")
            result.mark_completed(ActionStatus.FAILED, e.message, error_code="FILE_EXISTS")
            return result
        except Exception as e:
            logger.error(f"Filesystem action [{request.action_id}] failed: {e}", exc_info=True)
            result.mark_completed(ActionStatus.FAILED, str(e), error_code="FILESYSTEM_ERROR")
            return result

    def _execute_find_file(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        raw_dir = req.parameters.get("directory", "Downloads")
        pattern = req.parameters.get("pattern", "*.*")
        criterion = req.parameters.get("criterion", "latest")

        target_dir = self.policy.resolve_and_validate_path(raw_dir, must_exist=True, operation_name="find_file")
        if not target_dir.is_dir():
            res.mark_completed(ActionStatus.FAILED, f"'{target_dir}' is not a directory.", error_code="NOT_A_DIRECTORY")
            return res

        matched_files = [f for f in target_dir.glob(pattern) if f.is_file()]
        if not matched_files:
            res.mark_completed(ActionStatus.FAILED, f"No files matching '{pattern}' found in '{target_dir.name}'.", error_code="FILE_NOT_FOUND")
            return res

        # Sort files based on criterion
        if criterion == "latest":
            matched_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        found_path = matched_files[0]
        evidence = {
            "found_path": str(found_path),
            "filename": found_path.name,
            "size_bytes": found_path.stat().st_size,
            "modified_time": found_path.stat().st_mtime,
        }
        res.mark_completed(ActionStatus.SUCCESS, f"Found file '{found_path.name}'.", evidence=evidence)
        return res

    def _execute_read_file(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        raw_path = req.parameters.get("file_path") or req.parameters.get("path") or req.target.name
        max_bytes = int(req.parameters.get("max_bytes", 4096))

        file_p = self.policy.resolve_and_validate_path(raw_path, must_exist=True, operation_name="read_file")
        if not file_p.is_file():
            res.mark_completed(ActionStatus.FAILED, f"'{file_p}' is not a file.", error_code="NOT_A_FILE")
            return res

        with open(file_p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)

        evidence = {
            "file_path": str(file_p),
            "size_bytes": file_p.stat().st_size,
            "content_snippet": content[:200],
        }
        res.mark_completed(ActionStatus.SUCCESS, f"Successfully read file '{file_p.name}'.", evidence=evidence)
        return res

    def _execute_create_folder(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        raw_path = req.parameters.get("folder_path") or req.parameters.get("path") or req.target.name
        folder_p = self.policy.resolve_and_validate_path(raw_path, must_exist=False, operation_name="create_folder")

        if folder_p.exists():
            if folder_p.is_dir():
                evidence = {"folder_path": str(folder_p), "created": False, "existed": True}
                res.mark_completed(ActionStatus.SUCCESS, f"Folder '{folder_p.name}' already exists.", evidence=evidence)
                return res
            else:
                raise FileCollisionError(str(folder_p))

        folder_p.mkdir(parents=True, exist_ok=True)
        evidence = {"folder_path": str(folder_p), "created": True}
        res.mark_completed(ActionStatus.SUCCESS, f"Created folder '{folder_p.name}'.", evidence=evidence)
        return res

    def _execute_rename_file(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        raw_src = req.parameters.get("source_path") or req.parameters.get("source") or req.parameters.get("path") or req.target.name
        new_name = req.parameters.get("new_name")
        if not new_name:
            res.mark_completed(ActionStatus.FAILED, "Missing 'new_name' parameter.", error_code="INVALID_PARAMETER")
            return res

        self.policy.validate_filename(new_name)
        src_p = self.policy.resolve_and_validate_path(raw_src, must_exist=True, operation_name="rename_file")
        dest_p = src_p.parent / new_name

        if dest_p.exists() and dest_p != src_p:
            raise FileCollisionError(str(dest_p))

        src_p.rename(dest_p)
        evidence = {
            "source_path": str(src_p),
            "destination_path": str(dest_p),
            "new_name": new_name,
        }
        res.mark_completed(ActionStatus.SUCCESS, f"Renamed '{src_p.name}' to '{new_name}'.", evidence=evidence)
        return res

    def _execute_move_file(self, req: ActionRequest, res: ActionResult) -> ActionResult:
        raw_src = req.parameters.get("source_path") or req.target.name
        raw_dest = req.parameters.get("destination_path")
        if not raw_dest:
            res.mark_completed(ActionStatus.FAILED, "Missing 'destination_path' parameter.", error_code="INVALID_PARAMETER")
            return res

        src_p = self.policy.resolve_and_validate_path(raw_src, must_exist=True, operation_name="move_file")
        dest_dir_p = self.policy.resolve_and_validate_path(raw_dest, must_exist=False, operation_name="move_file_dest")

        # Auto-create destination folder if permitted
        if not dest_dir_p.exists():
            dest_dir_p.mkdir(parents=True, exist_ok=True)

        target_file_dest = dest_dir_p / src_p.name
        if target_file_dest.exists() and target_file_dest != src_p:
            raise FileCollisionError(str(target_file_dest))

        shutil.move(str(src_p), str(target_file_dest))
        evidence = {
            "source_path": str(src_p),
            "destination_path": str(target_file_dest),
            "destination_dir": str(dest_dir_p),
        }
        res.mark_completed(ActionStatus.SUCCESS, f"Moved '{src_p.name}' to '{dest_dir_p.name}'.", evidence=evidence)
        return res
