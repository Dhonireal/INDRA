"""
VisionPilot Capability Registry and Definitions.

Defines the universe of system and agent capabilities known to VisionPilot.
Provides explicit capability metadata:
- Name and Category
- Availability (Observation is active; Action execution is Phase 7+ schema only)
- Default Risk Level
- Confirmation requirement
- Reversibility
- Supported parameter schema
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from app.agent.task_schema import RiskLevel


class CapabilityCategory(str, Enum):
    OBSERVATION = "OBSERVATION"      # Screen inspection, OCR, element discovery (ACTIVE)
    INTERACTION = "INTERACTION"      # Click, type, press key (PHASE 7+ SCHEMA ONLY)
    APPLICATION = "APPLICATION"      # Launch app, switch window (PHASE 7+ SCHEMA ONLY)
    FILE_SYSTEM = "FILE_SYSTEM"      # Find, read, move, rename, delete (PHASE 7+ SCHEMA ONLY)
    SYSTEM = "SYSTEM"                # Sleep, wait, notification
    UNSUPPORTED = "UNSUPPORTED"      # Capabilities that are forbidden or not implemented


@dataclass
class CapabilityDefinition:
    """Strongly typed declaration of an agent capability."""
    name: str
    category: CapabilityCategory
    description: str
    available: bool = False             # True ONLY if currently executable
    enabled: bool = True
    default_risk: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    reversible: bool = True
    supported_parameters: Dict[str, str] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "available": self.available,
            "enabled": self.enabled,
            "default_risk": self.default_risk.value,
            "requires_confirmation": self.requires_confirmation,
            "reversible": self.reversible,
            "supported_parameters": self.supported_parameters,
        }


class CapabilityRegistry:
    """Registry maintaining authoritative capabilities and schemas for the planner."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityDefinition] = {}
        self._register_default_capabilities()

    def _register_default_capabilities(self) -> None:
        """Initializes standard capabilities with strict Phase 6 availability flags."""
        # 1. Observation Capabilities (IMPLEMENTED IN PHASE 5 - AVAILABLE FOR PERCEPTION)
        self.register(CapabilityDefinition(
            name="OBSERVE_SCREEN",
            category=CapabilityCategory.OBSERVATION,
            description="Capture and inspect desktop screen state, windows, and active visual content.",
            available=True,
            default_risk=RiskLevel.SAFE,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"scope": "str (ACTIVE_WINDOW | PRIMARY_SCREEN)"}
        ))
        self.register(CapabilityDefinition(
            name="FIND_UI_ELEMENT",
            category=CapabilityCategory.OBSERVATION,
            description="Locate accessible UI elements or text regions on the screen.",
            available=True,
            default_risk=RiskLevel.SAFE,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"role": "str", "name": "str", "automation_id": "str"}
        ))
        self.register(CapabilityDefinition(
            name="VERIFY_STATE",
            category=CapabilityCategory.OBSERVATION,
            description="Inspect the screen or system state to verify the outcome of a prior step.",
            available=True,
            default_risk=RiskLevel.SAFE,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"expectation": "str", "target": "str"}
        ))

        # 2. UI Interaction Capabilities (IMPLEMENTED IN PHASE 7)
        self.register(CapabilityDefinition(
            name="CLICK_UI_ELEMENT",
            category=CapabilityCategory.INTERACTION,
            description="Simulate mouse click on an accessible UI control.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"button": "str (left | right | double)", "modifier": "str"}
        ))
        self.register(CapabilityDefinition(
            name="DOUBLE_CLICK_UI_ELEMENT",
            category=CapabilityCategory.INTERACTION,
            description="Simulate mouse double-click on an accessible UI control.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"button": "str"}
        ))
        self.register(CapabilityDefinition(
            name="TYPE_TEXT",
            category=CapabilityCategory.INTERACTION,
            description="Type text into a focused input element.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"text": "str", "clear_first": "bool"}
        ))
        self.register(CapabilityDefinition(
            name="PRESS_KEY",
            category=CapabilityCategory.INTERACTION,
            description="Press an allowed keyboard key or navigation key.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"key": "str"}
        ))
        self.register(CapabilityDefinition(
            name="HOTKEY",
            category=CapabilityCategory.INTERACTION,
            description="Press an allowlisted keyboard shortcut combination.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"hotkey": "str"}
        ))
        self.register(CapabilityDefinition(
            name="SCROLL",
            category=CapabilityCategory.INTERACTION,
            description="Scroll the active window or target control.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"direction": "str (up | down)", "amount": "int"}
        ))

        # 3. Application Control Capabilities (IMPLEMENTED IN PHASE 7)
        self.register(CapabilityDefinition(
            name="LAUNCH_APPLICATION",
            category=CapabilityCategory.APPLICATION,
            description="Launch an allowlisted desktop application.",
            available=True,
            default_risk=RiskLevel.MEDIUM,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"app_name": "str", "arguments": "list[str]"}
        ))
        self.register(CapabilityDefinition(
            name="SWITCH_WINDOW",
            category=CapabilityCategory.APPLICATION,
            description="Bring a specific window to the foreground.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"window_title": "str", "hwnd": "int"}
        ))
        self.register(CapabilityDefinition(
            name="FOCUS_WINDOW",
            category=CapabilityCategory.APPLICATION,
            description="Focus an identified window safely.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"window_title": "str", "hwnd": "int"}
        ))

        # 4. File System Capabilities (IMPLEMENTED IN PHASE 7)
        self.register(CapabilityDefinition(
            name="FIND_FILE",
            category=CapabilityCategory.FILE_SYSTEM,
            description="Search for a file matching search criteria in user directories.",
            available=True,
            default_risk=RiskLevel.SAFE,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"directory": "str", "pattern": "str", "extension": "str"}
        ))
        self.register(CapabilityDefinition(
            name="READ_FILE",
            category=CapabilityCategory.FILE_SYSTEM,
            description="Read text metadata or contents from an authorized user file.",
            available=True,
            default_risk=RiskLevel.SAFE,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"file_path": "str", "max_bytes": "int"}
        ))
        self.register(CapabilityDefinition(
            name="CREATE_FOLDER",
            category=CapabilityCategory.FILE_SYSTEM,
            description="Create a folder in an authorized user directory.",
            available=True,
            default_risk=RiskLevel.LOW,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"folder_path": "str"}
        ))
        self.register(CapabilityDefinition(
            name="RENAME_FILE",
            category=CapabilityCategory.FILE_SYSTEM,
            description="Rename a file on disk within user directories.",
            available=True,
            default_risk=RiskLevel.MEDIUM,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"source_path": "str", "new_name": "str"}
        ))
        self.register(CapabilityDefinition(
            name="MOVE_FILE",
            category=CapabilityCategory.FILE_SYSTEM,
            description="Move a file from source path to destination directory.",
            available=True,
            default_risk=RiskLevel.MEDIUM,
            requires_confirmation=False,
            reversible=True,
            supported_parameters={"source_path": "str", "destination_path": "str"}
        ))
        self.register(CapabilityDefinition(
            name="DELETE_FILE",
            category=CapabilityCategory.FILE_SYSTEM,
            description="Permanent file deletion is strictly BLOCKED by policy.",
            available=False,
            enabled=False,
            default_risk=RiskLevel.BLOCKED,
            requires_confirmation=True,
            reversible=False,
            supported_parameters={"file_path": "str"}
        ))

        # 5. Blocked / Unsupported Capabilities (NEVER ALLOWED)
        self.register(CapabilityDefinition(
            name="EXECUTE_SHELL",
            category=CapabilityCategory.UNSUPPORTED,
            description="Execute arbitrary shell or PowerShell commands (BLOCKED by policy).",
            available=False,
            enabled=False,
            default_risk=RiskLevel.BLOCKED,
            requires_confirmation=True,
            reversible=False,
        ))
        self.register(CapabilityDefinition(
            name="EXECUTE_PYTHON",
            category=CapabilityCategory.UNSUPPORTED,
            description="Execute arbitrary Python scripts (BLOCKED by policy).",
            available=False,
            enabled=False,
            default_risk=RiskLevel.BLOCKED,
            requires_confirmation=True,
            reversible=False,
        ))
        self.register(CapabilityDefinition(
            name="SEND_EMAIL",
            category=CapabilityCategory.UNSUPPORTED,
            description="Send an email externally (UNSUPPORTED in current release).",
            available=False,
            enabled=False,
            default_risk=RiskLevel.HIGH,
            requires_confirmation=True,
            reversible=False,
        ))
        self.register(CapabilityDefinition(
            name="MAKE_PAYMENT",
            category=CapabilityCategory.UNSUPPORTED,
            description="Execute financial transaction (BLOCKED by safety policy).",
            available=False,
            enabled=False,
            default_risk=RiskLevel.BLOCKED,
            requires_confirmation=True,
            reversible=False,
        ))

    def register(self, capability: CapabilityDefinition) -> None:
        """Register a new or updated capability definition."""
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Optional[CapabilityDefinition]:
        """Retrieve capability definition by name."""
        return self._capabilities.get(name)

    def is_known(self, name: str) -> bool:
        """Check if capability is recognized in the registry."""
        return name in self._capabilities

    def is_available(self, name: str) -> bool:
        """Check if capability is currently executable."""
        cap = self._capabilities.get(name)
        return bool(cap and cap.available and cap.enabled)

    def is_blocked(self, name: str) -> bool:
        """Check if capability is categorically blocked by safety policy."""
        cap = self._capabilities.get(name)
        return bool(cap and cap.default_risk == RiskLevel.BLOCKED)

    def list_all(self) -> List[CapabilityDefinition]:
        """List all registered capabilities."""
        return list(self._capabilities.values())

    def list_available(self) -> List[CapabilityDefinition]:
        """List only available capabilities."""
        return [c for c in self._capabilities.values() if c.available and c.enabled]

    def to_schema_dict(self) -> Dict[str, Any]:
        """Export registry for structured reasoning prompts."""
        return {
            name: {
                "category": cap.category.value,
                "description": cap.description,
                "available": cap.available,
                "risk_level": cap.default_risk.value,
                "requires_confirmation": cap.requires_confirmation,
                "reversible": cap.reversible,
                "supported_parameters": cap.supported_parameters,
            }
            for name, cap in self._capabilities.items()
        }


# Global capability registry singleton
capability_registry = CapabilityRegistry()
