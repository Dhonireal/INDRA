"""
VisionPilot Demo Workspace Setup Script.

Creates a deterministic, safe, isolated demo environment under `demo_workspace/`
with synthetic research PDFs. Never touches real user directories.
"""
import os
import shutil
import time
from pathlib import Path


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo_workspace"
DOWNLOADS_DIR = DEMO_DIR / "Downloads"
RESEARCH_DIR = DEMO_DIR / "Research"
EXPECTED_DIR = DEMO_DIR / "expected"


def setup_demo_workspace() -> Path:
    """Sets up the isolated demo workspace with synthetic test documents."""
    # Ensure isolation - safety check
    resolved = DEMO_DIR.resolve()
    assert "demo_workspace" in resolved.parts, f"Safety violation: {resolved} is not demo_workspace"

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Create synthetic PDF 1: Older paper
    pdf1 = DOWNLOADS_DIR / "research-paper.pdf"
    if not pdf1.exists():
        pdf1.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
        # Set mtime to 1 hour ago
        old_time = time.time() - 3600
        os.utime(pdf1, (old_time, old_time))

    # 2. Create synthetic PDF 2: AI Notes
    pdf2 = DOWNLOADS_DIR / "ai-notes.pdf"
    if not pdf2.exists():
        pdf2.write_bytes(b"%PDF-1.4\n2 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
        mid_time = time.time() - 1800
        os.utime(pdf2, (mid_time, mid_time))

    # 3. Create synthetic PDF 3: Latest research (target of flagship demo)
    pdf3 = DOWNLOADS_DIR / "latest-research.pdf"
    pdf3.write_bytes(b"%PDF-1.4\n3 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")
    latest_time = time.time()
    os.utime(pdf3, (latest_time, latest_time))

    # Expected reference copy
    expected_pdf = EXPECTED_DIR / "Qualcomm-AI.pdf"
    expected_pdf.write_bytes(b"%PDF-1.4\n3 0 obj<<>>endobj\ntrailer<<>>\n%%EOF")

    # README in demo workspace
    readme = DEMO_DIR / "README.md"
    readme.write_text(
        "# VisionPilot Demo Workspace\n\n"
        "This directory is an isolated sandbox for VisionPilot automated demos.\n"
        "It contains synthetic demonstration PDFs and prevents any modifications\n"
        "to actual user documents or system folders.\n\n"
        "### Workflow Target:\n"
        "- Downloads/latest-research.pdf -> renamed to Qualcomm-AI.pdf -> moved to Research/\n",
        encoding="utf-8"
    )

    print(f"[DEMO SETUP] Isolated demo workspace ready at: {DEMO_DIR}")
    print(f"  - Downloads: {len(list(DOWNLOADS_DIR.glob('*.pdf')))} PDF files created")
    print(f"  - Latest file: {pdf3.name} (mtime: {time.ctime(latest_time)})")
    print(f"  - Research folder: {RESEARCH_DIR} (clean)")
    return DEMO_DIR


if __name__ == "__main__":
    setup_demo_workspace()
