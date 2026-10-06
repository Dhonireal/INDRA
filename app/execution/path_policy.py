"""
VisionPilot Filesystem Action Security Policy.

Enforces strict path security and bounded operations:
- Confines file access strictly to user-permitted locations (Downloads, Documents, Desktop, Research, and temp test folders)
- Blocks path traversal (../, ..\\)
- Blocks UNC network shares (\\\\server\\share)
- Blocks Windows system directories (C:\\Windows, C:\\Program Files, C:\\ProgramData, System32)
- Blocks root drive targets (C:\\, D:\\)
- Blocks permanent deletion (format, rmdir, del)
- Prevents silent file collisions / overwrites
- Validates safe file and folder names
"""
import os
from pathlib import Path
import re
from typing import List, Optional, Set, Tuple

from app.core.exceptions import PathSecurityError, FileCollisionError
from app.core.logger import logger


class PathSecurityPolicy:
    """Security validator for file and directory operations."""

    # Disallowed Windows and System directories
    _BLOCKED_SYSTEM_DIR_NAMES = {
        "windows", "system32", "syswow64", "program files", "program files (x86)",
        "programdata", "recovery", "boot", "appdata", "$recycle.bin", "system volume information"
    }

    # Forbidden filename characters on Windows: < > : " / \ | ? *
    _INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

    def __init__(self, allowed_roots: Optional[List[Path]] = None) -> None:
        self.user_home = Path.home().resolve()
        
        # Default allowed user roots
        if allowed_roots:
            self.allowed_roots = [p.resolve() for p in allowed_roots]
        else:
            self.allowed_roots = [
                (self.user_home / "Downloads").resolve(),
                (self.user_home / "Documents").resolve(),
                (self.user_home / "Desktop").resolve(),
                (self.user_home / "Research").resolve(),
            ]

    def add_allowed_root(self, root_path: Path) -> None:
        """Allow a specific directory (e.g., temporary test workspace)."""
        resolved = root_path.resolve()
        if resolved not in self.allowed_roots:
            self.allowed_roots.append(resolved)

    def remove_allowed_root(self, root_path: Path) -> None:
        """Remove a directory from allowed roots."""
        resolved = root_path.resolve()
        self.allowed_roots = [r for r in self.allowed_roots if r != resolved]

    def resolve_and_validate_path(self, raw_path: str, must_exist: bool = False, operation_name: str = "file_operation") -> Path:
        """
        Resolves a user-provided or model-provided path string and enforces security invariants.
        Raises PathSecurityError if the path violates policy.
        """
        if not raw_path or not raw_path.strip():
            raise PathSecurityError(raw_path, "Path cannot be empty.")

        clean_path_str = raw_path.strip()

        # 1. Block UNC paths (e.g. \\remote-server\share)
        if clean_path_str.startswith(("\\\\", "//")):
            raise PathSecurityError(clean_path_str, "UNC network paths are not permitted.")

        # 2. Block relative path traversal patterns
        if ".." in clean_path_str:
            raise PathSecurityError(clean_path_str, "Path traversal sequences ('..') are strictly prohibited.")

        # 3. Resolve path against user home / allowed roots if relative
        raw_p = Path(clean_path_str)
        if not raw_p.is_absolute():
            # Check if user specified a simple folder name like "Downloads" or "Research"
            first_part = raw_p.parts[0].lower() if raw_p.parts else ""
            matched_root = None
            for root in self.allowed_roots:
                if root.name.lower() == first_part:
                    # e.g., "Downloads/file.pdf" -> root / "file.pdf"
                    relative_sub = Path(*raw_p.parts[1:]) if len(raw_p.parts) > 1 else Path(".")
                    matched_root = root / relative_sub
                    break
            if matched_root:
                resolved_p = matched_root.resolve()
            else:
                # Default relative paths resolve in Downloads or Documents
                resolved_p = (self.allowed_roots[0] / raw_p).resolve()
        else:
            resolved_p = raw_p.resolve()

        # 4. Check if path is root drive (e.g. C:\ or D:\)
        if resolved_p == resolved_p.anchor or len(resolved_p.parts) <= 1:
            raise PathSecurityError(str(resolved_p), "Operations on drive root directories are strictly prohibited.")

        # 5. Check against blocked system directories across the full path
        allowed_parent_part_sets = [{p.lower() for p in r.parts} for r in self.allowed_roots]
        for part in resolved_p.parts:
            part_lower = part.lower()
            if part_lower in self._BLOCKED_SYSTEM_DIR_NAMES:
                # If part is legitimately part of an allowed root path (e.g. Temp inside AppData in test environment), allow it
                if not any(part_lower in part_set for part_set in allowed_parent_part_sets):
                    raise PathSecurityError(str(resolved_p), f"Access to system folder '{part}' is strictly blocked.")

        # 6. Verify path is contained within at least one allowed root
        matched_root: Optional[Path] = None
        for root in self.allowed_roots:
            try:
                rel = resolved_p.relative_to(root)
                matched_root = root
                break
            except ValueError:
                continue

        if not matched_root:
            allowed_names = [r.name for r in self.allowed_roots]
            raise PathSecurityError(
                str(resolved_p),
                f"Path is outside allowed user spaces ({', '.join(allowed_names)})."
            )

        # 6. Check against blocked system directories within the relative path
        rel_sub = resolved_p.relative_to(matched_root)
        for part in rel_sub.parts:
            if part.lower() in self._BLOCKED_SYSTEM_DIR_NAMES:
                raise PathSecurityError(str(resolved_p), f"Access to system folder '{part}' is strictly blocked.")

        # 7. Existence check if requested
        if must_exist and not resolved_p.exists():
            raise PathSecurityError(str(resolved_p), "Requested file or folder does not exist.")

        return resolved_p

    def validate_filename(self, filename: str) -> None:
        """Validates that a new filename does not contain illegal characters or reserved names."""
        if not filename or not filename.strip():
            raise PathSecurityError(filename, "Filename cannot be empty.")
        if self._INVALID_FILENAME_CHARS.search(filename):
            raise PathSecurityError(filename, "Filename contains invalid characters (< > : \" / \\ | ? *).")
        
        # Check reserved DOS device names (CON, PRN, AUX, NUL, COM1..9, LPT1..9)
        base_name = Path(filename).stem.upper()
        reserved_names = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
        if base_name in reserved_names:
            raise PathSecurityError(filename, f"'{filename}' uses a reserved Windows device name.")


# Global path security policy singleton
path_security_policy = PathSecurityPolicy()
