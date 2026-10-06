"""
VisionPilot Demo Workspace Reset Script.

Safely resets the isolated demo environment under `demo_workspace/`.
Guarantees never to touch or delete user folders outside `demo_workspace/`.
"""
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.setup_demo_workspace import setup_demo_workspace, DEMO_DIR, RESEARCH_DIR, DOWNLOADS_DIR


def reset_demo_workspace() -> None:
    """Safely cleans and restores the demo workspace to a deterministic state."""
    resolved = DEMO_DIR.resolve()
    # Guardrail check
    if "demo_workspace" not in resolved.parts:
        print(f"[DEMO RESET ERROR] Safety check failed: invalid path {resolved}")
        return
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    # Remove any existing files in Research directory
    if RESEARCH_DIR.exists():
        for item in RESEARCH_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    # Clean Downloads directory
    if DOWNLOADS_DIR.exists():
        for item in DOWNLOADS_DIR.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    # Re-populate deterministic state
    setup_demo_workspace()
    print("[DEMO RESET] Workspace reset completed successfully.")


def verify_demo_workspace() -> bool:
    """Verifies that the demo workspace is in the expected initial state."""
    if not DOWNLOADS_DIR.exists() or not RESEARCH_DIR.exists():
        return False
    pdfs = list(DOWNLOADS_DIR.glob("*.pdf"))
    latest = DOWNLOADS_DIR / "latest-research.pdf"
    clean_research = len(list(RESEARCH_DIR.iterdir())) == 0
    return len(pdfs) == 3 and latest.exists() and clean_research


if __name__ == "__main__":
    reset_demo_workspace()
    valid = verify_demo_workspace()
    print(f"[DEMO VERIFY] Initial state verified: {valid}")
