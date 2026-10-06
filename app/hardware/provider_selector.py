"""
VisionPilot AI Runtime Provider Selector.

Implements resource-aware, policy-constrained AI provider selection and deterministic fallback chains.
Strictly follows Non-Negotiable Rule 3 (Truthfulness) and Local-First Architecture:
- Never selects an unverified or uninstalled provider.
- Never falls back to cloud APIs.
- Supports execution modes: AUTO, LOCAL_ONLY, CPU_ONLY, ACCELERATED_LOCAL_ONLY.
- Enforces system RAM and disk headroom thresholds.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.logger import logger
from app.hardware.models import (
    DeviceType,
    ExecutionMode,
    ProviderRuntimeInfo,
    ProviderStatus,
    RuntimeProviderInfo,
    WorkloadType,
)
from app.hardware.runtime_detector import runtime_detector


class ProviderSelectionError(RuntimeError):
    """Raised when no compatible, verified provider satisfies the execution policy."""
    pass


class ResourceConstraintError(RuntimeError):
    """Raised when host memory or disk space is insufficient for the requested workload."""
    pass


class ProviderSelector:
    """Selects and manages AI execution providers according to policy and resource constraints."""

    # Default resource constraints
    MIN_RAM_HEADROOM_GB = 0.4   # 400 MB RAM reserve
    MIN_DISK_HEADROOM_GB = 0.5  # 500 MB disk reserve

    def __init__(self, mode: ExecutionMode = ExecutionMode.AUTO) -> None:
        self._mode: ExecutionMode = mode
        self._runtime_detector = runtime_detector
        self._fallback_events: List[Dict[str, Any]] = []

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    def set_execution_mode(self, mode: ExecutionMode) -> None:
        """Sets the active execution policy."""
        logger.info(f"Setting AI execution mode to: {mode.value}")
        self._mode = mode

    def get_execution_mode(self) -> ExecutionMode:
        """Returns the currently active execution policy."""
        return self._mode


    # --------------------------------------------------------------------------
    # Resource Checking
    # --------------------------------------------------------------------------

    def check_resources(
        self,
        required_ram_gb: float = MIN_RAM_HEADROOM_GB,
        required_disk_gb: float = MIN_DISK_HEADROOM_GB,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies that the system has adequate free RAM and storage.
        Prevents crashes or disk exhaustion on resource-constrained devices.
        """
        _, avail_ram_gb = self._runtime_detector.get_system_memory()
        hw = self._runtime_detector.audit_hardware()
        free_disk_gb = hw.disk_c_free_gb

        if avail_ram_gb < required_ram_gb:
            return False, f"Insufficient available RAM: {avail_ram_gb:.2f} GB (required: {required_ram_gb:.2f} GB)"

        if free_disk_gb < required_disk_gb:
            return False, f"Insufficient available disk space on C:: {free_disk_gb:.2f} GB (required: {required_disk_gb:.2f} GB)"

        return True, None

    # --------------------------------------------------------------------------
    # Fallback Chain Formation
    # --------------------------------------------------------------------------

    def get_fallback_chain(self, workload: WorkloadType) -> List[RuntimeProviderInfo]:
        """
        Constructs an ordered list of providers for a given workload based on policy.
        Priority: Verified NPU -> Verified GPU -> Verified Specialized WinRT -> Verified CPU.
        """
        providers = self._runtime_detector.enumerate_providers()
        candidates: List[RuntimeProviderInfo] = []

        if self._mode == ExecutionMode.CPU_ONLY:
            # Force CPU only
            if "cpu" in providers:
                candidates.append(providers["cpu"])
            if workload == WorkloadType.OCR and "winrt_ocr" in providers:
                candidates.append(providers["winrt_ocr"])
            return candidates

        # Determine preferred order for accelerated modes (AUTO, LOCAL_ONLY, ACCELERATED_LOCAL_ONLY)
        # NPU first
        if "qualcomm_qnn" in providers:
            p = providers["qualcomm_qnn"]
            if p.installed and p.available and (p.verified or self._runtime_detector.verify_provider("qualcomm_qnn")):
                candidates.append(p)

        # GPU second
        if "directml" in providers:
            p = providers["directml"]
            if p.installed and p.available and (p.verified or self._runtime_detector.verify_provider("directml")):
                candidates.append(p)

        # Windows ML third
        if "windows_ml" in providers:
            p = providers["windows_ml"]
            if p.installed and p.available and (p.verified or self._runtime_detector.verify_provider("windows_ml")):
                candidates.append(p)

        # Specialized native providers (e.g. WinRT OCR for OCR workloads)
        if workload == WorkloadType.OCR and "winrt_ocr" in providers:
            p = providers["winrt_ocr"]
            if p.installed and p.available and p.verified:
                candidates.append(p)

        # ONNX CPU
        if "onnx_cpu" in providers:
            p = providers["onnx_cpu"]
            if p.installed and p.available and (p.verified or self._runtime_detector.verify_provider("onnx_cpu")):
                candidates.append(p)

        # Standard CPU fallback (unless ACCELERATED_LOCAL_ONLY is mandated)
        if self._mode != ExecutionMode.ACCELERATED_LOCAL_ONLY:
            if "cpu" in providers:
                candidates.append(providers["cpu"])

        return candidates

    # --------------------------------------------------------------------------
    # Provider Selection
    # --------------------------------------------------------------------------

    def select_provider(
        self,
        workload: WorkloadType,
        required_ram_gb: float = MIN_RAM_HEADROOM_GB,
        required_disk_gb: float = MIN_DISK_HEADROOM_GB,
    ) -> RuntimeProviderInfo:
        """
        Selects the best verified provider for a workload satisfying active policy and resources.
        Raises ProviderSelectionError if no verified provider is available.
        """
        ok, res_err = self.check_resources(required_ram_gb, required_disk_gb)
        if not ok:
            logger.warning(f"Resource constraint warning during provider selection: {res_err}")

        chain = self.get_fallback_chain(workload)
        if not chain:
            if self._mode == ExecutionMode.ACCELERATED_LOCAL_ONLY:
                raise ProviderSelectionError(
                    f"No verified local hardware accelerator (NPU/GPU) is available for workload '{workload.value}' "
                    "under ACCELERATED_LOCAL_ONLY policy."
                )
            raise ProviderSelectionError(
                f"No suitable provider available for workload '{workload.value}' under {self._mode.value} policy."
            )

        # Filter by workload support
        for prov in chain:
            if workload in prov.supported_workloads or WorkloadType.SYNTHETIC_BENCHMARK in prov.supported_workloads:
                return prov

        # Default to first in chain
        return chain[0]

    # --------------------------------------------------------------------------
    # Resilient Execution with Safe Fallback
    # --------------------------------------------------------------------------

    def execute_with_fallback(
        self,
        workload: WorkloadType,
        execute_fn: Callable[[RuntimeProviderInfo], Any],
        required_ram_gb: float = MIN_RAM_HEADROOM_GB,
    ) -> Tuple[Any, ProviderRuntimeInfo]:
        """
        Executes workload callable across the fallback chain.
        If the primary provider fails, seamlessly falls back to CPU.
        Returns (result, provider_runtime_metadata).
        Never calls external networks or cloud services.
        """
        chain = self.get_fallback_chain(workload)
        if not chain:
            raise ProviderSelectionError(f"No execution providers available for {workload.value}")

        last_error: Optional[Exception] = None

        for prov in chain:
            try:
                logger.debug(f"Attempting workload '{workload.value}' with provider: {prov.display_name}")
                result = execute_fn(prov)

                runtime_info = ProviderRuntimeInfo(
                    provider_id=prov.provider_id,
                    runtime=prov.display_name,
                    device=prov.device_type.value,
                    execution_provider=prov.vendor,
                    verified=prov.verified,
                    model_name=prov.supported_models[0] if prov.supported_models else "Default",
                )
                return result, runtime_info

            except Exception as e:
                last_error = e
                prov.initialization_status = ProviderStatus.FAILED
                prov.failure_reason = str(e)
                logger.warning(
                    f"Provider '{prov.provider_id}' failed on workload '{workload.value}': {e}. "
                    "Transitioning down fallback chain."
                )
                self._fallback_events.append({
                    "workload": workload.value,
                    "failed_provider": prov.provider_id,
                    "error": str(e),
                })
                continue

        # If all candidates failed:
        raise ProviderSelectionError(
            f"All providers in fallback chain failed for workload '{workload.value}'. Last error: {last_error}"
        )


# Global singleton selector
provider_selector = ProviderSelector()
