"""
VisionPilot Configuration Management.

Loads configuration from environment variables and optional .env file with
strongly typed dataclass representation.
"""
from dataclasses import dataclass, field
import os
import sys
from pathlib import Path
from typing import Literal

AccelerationPreference = Literal["auto", "npu", "directml", "cpu"]


def _load_dotenv(filepath: Path) -> None:
    """Simple, zero-dependency .env file parser."""
    if not filepath.exists() or not filepath.is_file():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("\"'")
                if key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


@dataclass
class SafetyConfig:
    auto_approve_low_risk: bool = True
    confirm_medium_risk: bool = False
    confirm_high_risk: bool = True
    max_consecutive_retries: int = 3
    blocked_commands: list[str] = field(default_factory=lambda: [
        "format", "diskpart", "regedit", "powershell -enc",
        "drop database", "rmdir /s /q c:\\windows", "del /f /s /q c:\\windows"
    ])


@dataclass
class CommandConfig:
    max_command_length: int = 2000
    min_command_length: int = 1
    enable_history_persistence: bool = True


@dataclass
class VoiceConfig:
    sample_rate: int = 16000
    max_duration_seconds: int = 15
    auto_submit: bool = True
    provider: str = "local"
    language: str = "en-US"
    store_raw_audio: bool = False


@dataclass
class PerceptionConfig:
    timeout_seconds: float = 5.0
    enable_ocr: bool = True
    enable_uia: bool = True
    lazy_ocr: bool = True
    default_scope: str = "active_window"
    redact_sensitive_fields: bool = True
    store_screenshots: bool = False
    cache_ttl_seconds: float = 1.0
    ocr_confidence_threshold: float = 0.5


@dataclass
class PlannerConfig:
    provider: str = "local"  # "local", "mock"
    planning_timeout_seconds: float = 10.0
    max_repair_retries: int = 1
    max_steps_per_plan: int = 20
    model_name: str = "VisionPilot-Deterministic-Planner-v1"
    runtime: str = "Deterministic Rule-Engine / SLM Abstraction"
    accelerator: str = "CPU"


@dataclass
class ExecutorConfig:
    enabled: bool = True
    action_timeout_seconds: float = 10.0
    confirmation_timeout_seconds: float = 60.0
    max_retries: int = 1
    max_scroll_amount: int = 10
    allow_folder_creation: bool = True
    allowed_app_whitelist: list[str] = field(default_factory=lambda: [
        "notepad", "calculator", "explorer", "edge", "settings"
    ])


@dataclass
class VerificationConfig:
    enabled: bool = True
    default_timeout_seconds: float = 3.0
    poll_interval_seconds: float = 0.1
    stability_window_seconds: float = 0.2
    require_file_hash_verification: bool = False
    ocr_confidence_threshold: float = 0.6
    enable_screenshot_comparison: bool = False


@dataclass
class RecoveryConfig:
    enabled: bool = True
    max_recovery_depth: int = 3
    max_ui_retries: int = 1
    max_readonly_retries: int = 2
    max_reperception_attempts: int = 1
    allow_blind_retries_for_side_effects: bool = False  # Strictly False (Side-effect safety)
    auto_escalate_uncertain_to_user: bool = True


@dataclass
class HistoryConfig:
    enabled: bool = True
    retention_days: int = 30  # Default: 30 days (0 = retain indefinitely)
    max_tasks: int = 1000     # Maximum tasks stored in local history
    redact_sensitive_data: bool = True
    store_screen_metadata_only: bool = True


@dataclass
class HardwareConfig:
    acceleration_mode: AccelerationPreference = "auto"
    enable_profiling: bool = True
    benchmark_iterations: int = 3


@dataclass
class AppConfig:
    app_name: str = "VisionPilot"
    version: str = "0.1.0"
    tagline: str = "See. Understand. Act. Verify."
    env: str = "development"
    
    # Command
    command: CommandConfig = field(default_factory=CommandConfig)
    
    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path = field(default_factory=lambda: Path("data"))
    logs_dir: Path = field(default_factory=lambda: Path("logs"))
    models_dir: Path = field(default_factory=lambda: Path("models"))
    db_path: Path = field(default_factory=lambda: Path("data/visionpilot.db"))

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = True
    log_file_name: str = "visionpilot.log"

    # Safety
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    # Voice (Phase 4)
    voice: VoiceConfig = field(default_factory=VoiceConfig)

    # Perception (Phase 5)
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)

    # Hardware
    hardware: HardwareConfig = field(default_factory=HardwareConfig)

    # Planner (Phase 6)
    planner: PlannerConfig = field(default_factory=PlannerConfig)

    # Executor (Phase 7)
    executor: ExecutorConfig = field(default_factory=ExecutorConfig)

    # Verification & Recovery (Phase 8)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)

    # Task History & Audit Trail (Phase 9)
    history: HistoryConfig = field(default_factory=HistoryConfig)

    # Optional Fallback
    fallback_provider: str = "none"
    fallback_api_key: str = ""

    def __post_init__(self) -> None:
        # Resolve absolute paths
        if not self.data_dir.is_absolute():
            self.data_dir = self.base_dir / self.data_dir
        if not self.logs_dir.is_absolute():
            self.logs_dir = self.base_dir / self.logs_dir
        if not self.models_dir.is_absolute():
            self.models_dir = self.base_dir / self.models_dir
        if not self.db_path.is_absolute():
            self.db_path = self.base_dir / self.db_path

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


def get_application_paths(env: str = "development") -> tuple[Path, Path, Path, Path, Path]:
    """
    Returns (base_dir, data_dir, logs_dir, models_dir, db_path)
    respecting frozen / installed / portable / development mode.
    """
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parent.parent.parent

    is_portable = os.environ.get("VISIONPILOT_PORTABLE") == "1" or (app_dir / "portable.txt").exists()

    if is_frozen and not is_portable:
        # Standard Windows Installed Application Mode: store user data in %LOCALAPPDATA%\VisionPilot
        user_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "VisionPilot"
        data_dir = user_root / "data"
        logs_dir = user_root / "logs"
        models_dir = user_root / "models"
        db_path = data_dir / "visionpilot.db"
    elif env == "production" and not is_portable and not is_frozen and "LOCALAPPDATA" in os.environ and os.environ.get("VISIONPILOT_USE_USERDATA") == "1":
        user_root = Path(os.environ["LOCALAPPDATA"]) / "VisionPilot"
        data_dir = user_root / "data"
        logs_dir = user_root / "logs"
        models_dir = user_root / "models"
        db_path = data_dir / "visionpilot.db"
    else:
        # Development or Portable Mode
        data_dir = app_dir / "data"
        logs_dir = app_dir / "logs"
        models_dir = app_dir / "models"
        db_path = data_dir / "visionpilot.db"

    return app_dir, data_dir, logs_dir, models_dir, db_path


def load_config() -> AppConfig:
    """Load configuration from environment and .env."""
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent

    _load_dotenv(base_dir / ".env")

    env = os.environ.get("VISIONPILOT_ENV", "production" if is_frozen else "development")
    log_level = os.environ.get("VISIONPILOT_LOG_LEVEL", "INFO").upper()
    log_to_file = os.environ.get("VISIONPILOT_LOG_TO_FILE", "true").lower() in ("true", "1", "yes")

    app_dir, data_dir, logs_dir, models_dir, db_path = get_application_paths(env)

    auto_low = os.environ.get("VISIONPILOT_AUTO_APPROVE_LOW_RISK", "true").lower() in ("true", "1", "yes")
    confirm_med = os.environ.get("VISIONPILOT_CONFIRM_MEDIUM_RISK", "false").lower() in ("true", "1", "yes")
    confirm_high = os.environ.get("VISIONPILOT_CONFIRM_HIGH_RISK", "true").lower() in ("true", "1", "yes")

    max_cmd_len = int(os.environ.get("VISIONPILOT_MAX_COMMAND_LENGTH", "2000"))
    cmd_cfg = CommandConfig(max_command_length=max_cmd_len)

    accel_mode = os.environ.get("VISIONPILOT_ACCELERATION_MODE", "auto").lower()
    if accel_mode not in ("auto", "npu", "directml", "cpu"):
        accel_mode = "auto"

    safety = SafetyConfig(
        auto_approve_low_risk=auto_low,
        confirm_medium_risk=confirm_med,
        confirm_high_risk=confirm_high
    )
    hardware = HardwareConfig(
        acceleration_mode=accel_mode  # type: ignore[arg-type]
    )

    voice = VoiceConfig(
        max_duration_seconds=int(os.environ.get("VISIONPILOT_VOICE_MAX_DURATION", "15")),
        language=os.environ.get("VISIONPILOT_VOICE_LANGUAGE", "en-US")
    )

    perception = PerceptionConfig(
        timeout_seconds=float(os.environ.get("VISIONPILOT_PERCEPTION_TIMEOUT", "5.0")),
        enable_ocr=os.environ.get("VISIONPILOT_ENABLE_OCR", "true").lower() in ("true", "1", "yes"),
        enable_uia=os.environ.get("VISIONPILOT_ENABLE_UIA", "true").lower() in ("true", "1", "yes"),
        lazy_ocr=os.environ.get("VISIONPILOT_LAZY_OCR", "true").lower() in ("true", "1", "yes"),
        store_screenshots=os.environ.get("VISIONPILOT_STORE_SCREENSHOTS", "false").lower() in ("true", "1", "yes")
    )

    planner = PlannerConfig(
        provider=os.environ.get("VISIONPILOT_PLANNER_PROVIDER", "local").lower(),
        planning_timeout_seconds=float(os.environ.get("VISIONPILOT_PLANNING_TIMEOUT", "10.0")),
        max_repair_retries=int(os.environ.get("VISIONPILOT_PLANNER_MAX_REPAIRS", "1")),
        max_steps_per_plan=int(os.environ.get("VISIONPILOT_PLANNER_MAX_STEPS", "20"))
    )

    executor = ExecutorConfig(
        enabled=os.environ.get("VISIONPILOT_EXECUTOR_ENABLED", "true").lower() in ("true", "1", "yes"),
        action_timeout_seconds=float(os.environ.get("VISIONPILOT_ACTION_TIMEOUT", "10.0")),
        confirmation_timeout_seconds=float(os.environ.get("VISIONPILOT_CONFIRMATION_TIMEOUT", "60.0")),
    )

    return AppConfig(
        base_dir=app_dir,
        data_dir=data_dir,
        logs_dir=logs_dir,
        models_dir=models_dir,
        db_path=db_path,
        env=env,
        log_level=log_level,
        log_to_file=log_to_file,
        command=cmd_cfg,
        safety=safety,
        voice=voice,
        perception=perception,
        hardware=hardware,
        planner=planner,
        executor=executor,
        fallback_provider=os.environ.get("VISIONPILOT_FALLBACK_PROVIDER", "none"),
        fallback_api_key=os.environ.get("VISIONPILOT_FALLBACK_API_KEY", "")
    )


# Global configuration instance
config = load_config()
