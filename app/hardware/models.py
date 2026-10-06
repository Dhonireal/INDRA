"""
VisionPilot Hardware and Runtime Capability Models.

Provides strongly-typed schemas for hardware detection, runtime provider capabilities,
execution modes, provider statuses, benchmark metrics, and execution telemetry.
Strictly adheres to Truthfulness Rule 3 (No Fabricated AI Acceleration).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ProviderStatus(str, Enum):
    """Lifecycle status of an AI/ML runtime provider."""
    NOT_INSTALLED = "NOT_INSTALLED"
    AVAILABLE = "AVAILABLE"
    SUPPORTED = "SUPPORTED"
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"
    DISABLED = "DISABLED"


class ExecutionMode(str, Enum):
    """User-configurable AI runtime execution policy."""
    AUTO = "AUTO"                            # Select best verified local provider
    LOCAL_ONLY = "LOCAL_ONLY"                # Strictly local providers (accelerator or CPU)
    CPU_ONLY = "CPU_ONLY"                    # Force standard CPU execution
    ACCELERATED_LOCAL_ONLY = "ACCELERATED_LOCAL_ONLY"  # Accelerator only; fail if none verified


class DeviceType(str, Enum):
    """Hardware target device classification."""
    CPU = "CPU"
    GPU = "GPU"
    NPU = "NPU"
    UNKNOWN = "UNKNOWN"


class WorkloadType(str, Enum):
    """Types of AI and processing workloads in VisionPilot."""
    OCR = "OCR"
    VISION_PREPROCESS = "VISION_PREPROCESS"
    REASONING_SLM = "REASONING_SLM"
    VOICE_STT = "VOICE_STT"
    SYNTHETIC_BENCHMARK = "SYNTHETIC_BENCHMARK"


@dataclass
class HardwareAuditReport:
    """Detailed hardware and operating environment snapshot."""
    cpu_name: str = "Unknown CPU"
    cpu_architecture: str = "ARM64"
    cpu_cores_logical: int = 1
    cpu_cores_physical: int = 1
    gpu_name: str = "Unknown GPU"
    gpu_vendor: str = "Unknown"
    npu_name: str = "Not Detected"
    npu_vendor: str = "None"
    npu_present: bool = False
    npu_os_status: str = "Unavailable"
    total_ram_gb: float = 0.0
    available_ram_gb: float = 0.0
    disk_c_total_gb: float = 0.0
    disk_c_free_gb: float = 0.0
    os_version: str = "Windows"
    os_arch: str = "ARM64"
    python_version: str = "3.14"
    python_arch: str = "64bit"
    is_emulated_x64: bool = False
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def ram_total_gb(self) -> float:
        return self.total_ram_gb

    @property
    def ram_available_gb(self) -> float:
        return self.available_ram_gb

    @property
    def platform_summary(self) -> str:
        return f"{self.cpu_name} | {self.gpu_name} | NPU: {self.npu_name if self.npu_present else 'None'}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_name": self.cpu_name,
            "cpu_architecture": self.cpu_architecture,
            "cpu_cores_logical": self.cpu_cores_logical,
            "cpu_cores_physical": self.cpu_cores_physical,
            "gpu_name": self.gpu_name,
            "gpu_vendor": self.gpu_vendor,
            "npu_name": self.npu_name,
            "npu_vendor": self.npu_vendor,
            "npu_present": self.npu_present,
            "npu_os_status": self.npu_os_status,
            "total_ram_gb": self.total_ram_gb,
            "available_ram_gb": self.available_ram_gb,
            "disk_c_total_gb": self.disk_c_total_gb,
            "disk_c_free_gb": self.disk_c_free_gb,
            "os_version": self.os_version,
            "os_arch": self.os_arch,
            "python_version": self.python_version,
            "python_arch": self.python_arch,
            "is_emulated_x64": self.is_emulated_x64,
            "platform_summary": self.platform_summary,
            "detected_at": self.detected_at,
        }


@dataclass
class RuntimeProviderInfo:
    """Capability model for a runtime execution provider."""
    provider_id: str
    display_name: str
    device_type: DeviceType
    vendor: str
    installed: bool = False
    available: bool = False
    verified: bool = False
    active: bool = False
    supported_models: List[str] = field(default_factory=list)
    supported_workloads: List[WorkloadType] = field(default_factory=list)
    initialization_status: ProviderStatus = ProviderStatus.NOT_INSTALLED
    failure_reason: Optional[str] = None
    version: str = "Unknown"
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "device_type": self.device_type.value,
            "vendor": self.vendor,
            "installed": self.installed,
            "available": self.available,
            "verified": self.verified,
            "active": self.active,
            "supported_models": self.supported_models,
            "supported_workloads": [w.value for w in self.supported_workloads],
            "initialization_status": self.initialization_status.value,
            "failure_reason": self.failure_reason,
            "version": self.version,
            "detected_at": self.detected_at,
        }


@dataclass
class ProviderRuntimeInfo:
    """Runtime metadata exposed by model providers during execution."""
    provider_id: str
    runtime: str
    device: str
    execution_provider: str
    verified: bool = False
    initialization_time_ms: float = 0.0
    model_name: str = "Default"
    model_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "runtime": self.runtime,
            "device": self.device,
            "execution_provider": self.execution_provider,
            "verified": self.verified,
            "initialization_time_ms": self.initialization_time_ms,
            "model_name": self.model_name,
            "model_version": self.model_version,
        }


@dataclass
class BenchmarkResult:
    """Measured performance metrics for a specific workload and provider."""
    benchmark_id: str = field(default_factory=lambda: f"bench-{uuid.uuid4().hex[:8]}")
    workload: WorkloadType = WorkloadType.SYNTHETIC_BENCHMARK
    provider: str = "CPU"
    runtime: str = "Native Python"
    device: str = "Qualcomm Oryon CPU"
    model: str = "Synthetic"
    iterations: int = 10
    warmup_iterations: int = 2
    first_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    throughput: float = 0.0  # Operations per second
    memory_before_mb: float = 0.0
    memory_after_mb: float = 0.0
    success: bool = False
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "workload": self.workload.value,
            "provider": self.provider,
            "runtime": self.runtime,
            "device": self.device,
            "model": self.model,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "first_latency_ms": round(self.first_latency_ms, 2),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "throughput": round(self.throughput, 2),
            "memory_before_mb": round(self.memory_before_mb, 2),
            "memory_after_mb": round(self.memory_after_mb, 2),
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp,
        }
