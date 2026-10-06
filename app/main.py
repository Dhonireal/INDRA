"""
VisionPilot Main Application Entry Point.

Initializes logging, configuration, device detection, and launches the desktop application.
"""
import sys
import os
from pathlib import Path
import argparse
from typing import Optional

# Ensure non-null stdout/stderr in windowed frozen mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication

from app.core.config import config
from app.core.logger import logger
from app.core.state import app_state
from app.hardware.device_detector import device_detector
from app.storage.database import init_db
from app.services.history_service import history_service
from app.ui.main_window import MainWindow


def bootstrap() -> None:
    """Performs pre-flight environment checks, database initialization, and startup crash recovery."""
    logger.info("Initializing VisionPilot system foundation...")
    logger.info(f"Environment: {config.env}")
    logger.info(f"Data directory: {config.data_dir}")
    logger.info(f"Logs directory: {config.logs_dir}")

    # Initialize SQLite tables and indexes
    init_db()

    # Startup crash recovery: detect and mark interrupted tasks from prior sessions
    history_service.recover_interrupted_tasks()

    # Detect hardware
    logger.info("Auditing device hardware...")
    hw_state = device_detector.detect()
    app_state.set_hardware(hw_state)

    logger.info(f"Detected CPU: {hw_state.cpu_name}")
    logger.info(f"Detected GPU: {hw_state.gpu_name}")
    logger.info(f"Detected NPU: {hw_state.npu_name} (Present: {hw_state.npu_present})")
    logger.info(f"Acceleration Tier: {hw_state.active_runtime}")


def main(argv: Optional[list[str]] = None) -> int:
    """Main application entrypoint."""
    parser = argparse.ArgumentParser(description="VisionPilot Desktop AI Agent")
    parser.add_argument("--check-only", action="store_true", help="Run startup audit and exit with status 0")
    parser.add_argument("--headless", action="store_true", help="Run without opening GUI window")
    args = parser.parse_args(argv)

    bootstrap()

    if args.check_only:
        logger.info("Startup check completed successfully.")
        return 0

    if args.headless:
        logger.info("Running in headless mode. State is IDLE.")
        return 0

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    logger.info("VisionPilot desktop main window launched successfully.")
    return app.exec()


if __name__ == "__main__":
    exit_code = main()
    os._exit(exit_code if exit_code is not None else 0)
