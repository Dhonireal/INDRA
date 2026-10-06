"""
VisionPilot Phase 10 Unit Tests — Snapdragon Runtime Detection, Benchmarking, and Telemetry.

Tests cover:
- Hardware audit (CPU/GPU/NPU detection)
- Runtime provider discovery and availability
- Resource constraint checking
- Fallback chain construction
- Execution mode enforcement
- Benchmark engine (all 4 workloads)
- Latency statistics (p50, p95, average)
- Memory telemetry
- BenchmarkResult data model
- Truthfulness invariants (no fabricated results)
- Provider selector policy enforcement
- CLI entry point
"""
import time
import math
import pytest
from unittest.mock import patch, MagicMock
from typing import List

from app.hardware.models import (
    BenchmarkResult,
    DeviceType,
    ExecutionMode,
    HardwareAuditReport,
    ProviderRuntimeInfo,
    ProviderStatus,
    RuntimeProviderInfo,
    WorkloadType,
)
from app.hardware.runtime_detector import RuntimeDetector
from app.hardware.provider_selector import ProviderSelector
from app.hardware.benchmark_engine import BenchmarkEngine


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def fresh_detector() -> RuntimeDetector:
    """Returns an uncached RuntimeDetector for each test."""
    d = RuntimeDetector()
    d._hw_cache = None
    d._provider_cache = None
    return d


@pytest.fixture
def fresh_selector() -> ProviderSelector:
    return ProviderSelector(mode=ExecutionMode.AUTO)


@pytest.fixture
def fresh_engine() -> BenchmarkEngine:
    return BenchmarkEngine()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Hardware Audit Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestHardwareAudit:
    def test_audit_hardware_returns_report(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert isinstance(report, HardwareAuditReport)

    def test_cpu_name_is_nonempty(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.cpu_name and len(report.cpu_name) > 0

    def test_ram_total_positive(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.ram_total_gb > 0.0

    def test_ram_available_positive(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.ram_available_gb >= 0.0

    def test_ram_available_lte_total(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.ram_available_gb <= report.ram_total_gb

    def test_gpu_name_is_nonempty(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.gpu_name and len(report.gpu_name) > 0

    def test_npu_present_is_bool(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert isinstance(report.npu_present, bool)

    def test_npu_name_nonempty_when_present(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        if report.npu_present:
            assert len(report.npu_name) > 0

    def test_disk_c_free_gb_nonnegative(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.disk_c_free_gb >= 0.0

    def test_platform_summary_nonempty(self, fresh_detector):
        report = fresh_detector.audit_hardware()
        assert report.platform_summary and len(report.platform_summary) > 0

    def test_hardware_cache_reused(self, fresh_detector):
        """Second call must return cached result without re-detecting."""
        r1 = fresh_detector.audit_hardware()
        r2 = fresh_detector.audit_hardware()
        assert r1 is r2, "Cache should return the same object instance"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Provider Discovery Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProviderDiscovery:
    def test_enumerate_providers_returns_nonempty_dict(self, fresh_detector):
        providers = fresh_detector.enumerate_providers()
        assert isinstance(providers, dict)
        assert len(providers) > 0

    def test_cpu_provider_always_present(self, fresh_detector):
        providers = fresh_detector.enumerate_providers()
        assert "cpu" in providers

    def test_cpu_provider_always_available(self, fresh_detector):
        providers = fresh_detector.enumerate_providers()
        cpu = providers["cpu"]
        assert cpu.available is True

    def test_all_providers_have_display_name(self, fresh_detector):
        providers = fresh_detector.enumerate_providers()
        for pid, p in providers.items():
            assert p.display_name and len(p.display_name) > 0, f"Provider {pid} missing display_name"

    def test_all_providers_have_provider_id(self, fresh_detector):
        providers = fresh_detector.enumerate_providers()
        for pid, p in providers.items():
            assert p.provider_id and len(p.provider_id) > 0

    def test_unavailable_providers_have_failure_reason(self, fresh_detector):
        providers = fresh_detector.enumerate_providers()
        for pid, p in providers.items():
            if not p.available:
                assert p.failure_reason is not None, (
                    f"Unavailable provider '{pid}' must have a failure_reason"
                )

    def test_provider_cache_reused(self, fresh_detector):
        p1 = fresh_detector.enumerate_providers()
        p2 = fresh_detector.enumerate_providers()
        assert p1 is p2

    def test_get_process_memory_mb_positive(self, fresh_detector):
        mem = fresh_detector.get_process_memory_mb()
        assert mem > 0.0, "Process memory must be positive"


# ──────────────────────────────────────────────────────────────────────────────
# 3. Provider Selector Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestProviderSelector:
    def test_default_mode_is_auto(self, fresh_selector):
        assert fresh_selector.mode == ExecutionMode.AUTO

    def test_get_execution_mode_matches_mode_property(self, fresh_selector):
        assert fresh_selector.get_execution_mode() == fresh_selector.mode

    def test_set_execution_mode_cpu_only(self, fresh_selector):
        fresh_selector.set_execution_mode(ExecutionMode.CPU_ONLY)
        assert fresh_selector.mode == ExecutionMode.CPU_ONLY

    def test_set_execution_mode_auto(self, fresh_selector):
        fresh_selector.set_execution_mode(ExecutionMode.AUTO)
        assert fresh_selector.mode == ExecutionMode.AUTO

    def test_set_and_get_execution_mode_round_trip(self, fresh_selector):
        for mode in ExecutionMode:
            fresh_selector.set_execution_mode(mode)
            assert fresh_selector.get_execution_mode() == mode

    def test_select_provider_returns_info(self, fresh_selector):
        result = fresh_selector.select_provider(WorkloadType.OCR)
        assert isinstance(result, RuntimeProviderInfo)

    def test_select_ocr_provider_available_when_winrt_present(self, fresh_selector):
        result = fresh_selector.select_provider(WorkloadType.OCR)
        assert result is not None

    def test_cpu_only_mode_selects_cpu_or_winrt(self, fresh_selector):
        fresh_selector.set_execution_mode(ExecutionMode.CPU_ONLY)
        for wl in WorkloadType:
            result = fresh_selector.select_provider(wl)
            assert result is not None
            assert result.provider_id in ("cpu", "winrt_ocr"), (
                f"CPU_ONLY mode returned unexpected provider: {result.provider_id}"
            )

    def test_check_resources_passes_with_adequate_memory(self, fresh_selector):
        ok, reason = fresh_selector.check_resources(required_ram_gb=0.1)
        assert ok is True, f"Resource check failed unexpectedly: {reason}"

    def test_check_resources_fails_with_excessive_demand(self, fresh_selector):
        ok, reason = fresh_selector.check_resources(required_ram_gb=999.0)
        assert ok is False
        assert reason is not None

    def test_fallback_chain_cpu_only_contains_only_cpu(self, fresh_selector):
        fresh_selector.set_execution_mode(ExecutionMode.CPU_ONLY)
        chain = fresh_selector.get_fallback_chain(WorkloadType.VISION_PREPROCESS)
        for p in chain:
            assert p.provider_id in ("cpu", "winrt_ocr")

    def test_fallback_chain_auto_not_empty(self, fresh_selector):
        fresh_selector.set_execution_mode(ExecutionMode.AUTO)
        chain = fresh_selector.get_fallback_chain(WorkloadType.REASONING_SLM)
        assert len(chain) > 0


# ──────────────────────────────────────────────────────────────────────────────
# 4. BenchmarkEngine Statistics Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBenchmarkEngineStatistics:
    def test_percentile_p50_of_sorted_list(self, fresh_engine):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        p50 = fresh_engine.calculate_percentile(data, 50.0)
        assert 2.5 <= p50 <= 3.5, f"Unexpected P50: {p50}"

    def test_percentile_p95_gte_p50(self, fresh_engine):
        data = [float(x) for x in range(1, 101)]
        p50 = fresh_engine.calculate_percentile(data, 50.0)
        p95 = fresh_engine.calculate_percentile(data, 95.0)
        assert p95 >= p50

    def test_percentile_single_element(self, fresh_engine):
        p = fresh_engine.calculate_percentile([42.0], 99.0)
        assert p == 42.0

    def test_percentile_empty_list_returns_zero(self, fresh_engine):
        p = fresh_engine.calculate_percentile([], 50.0)
        assert p == 0.0

    def test_benchmark_result_default_success_false(self):
        result = BenchmarkResult(
            workload=WorkloadType.SYNTHETIC_BENCHMARK,
            provider="test",
            runtime="mock",
            device="MockCPU",
            model="none",
        )
        assert result.success is False

    def test_benchmark_history_accumulates(self, fresh_engine):
        initial_count = len(fresh_engine.get_history())
        fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=2, warmup=1)
        assert len(fresh_engine.get_history()) == initial_count + 1

    def test_clear_history_empties_list(self, fresh_engine):
        fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=1, warmup=0)
        fresh_engine.clear_history()
        assert len(fresh_engine.get_history()) == 0


# ──────────────────────────────────────────────────────────────────────────────
# 5. Benchmark Workload Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestBenchmarkWorkloads:
    def test_synthetic_math_workload_succeeds(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=3, warmup=1)
        assert result.success is True

    def test_synthetic_math_average_positive(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=3, warmup=1)
        assert result.average_latency_ms > 0.0

    def test_synthetic_math_throughput_positive(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=3, warmup=1)
        assert result.throughput > 0.0

    def test_synthetic_math_p95_gte_p50(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=5, warmup=1)
        assert result.p95_latency_ms >= result.p50_latency_ms

    def test_vision_preprocess_workload_succeeds(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.VISION_PREPROCESS, iterations=3, warmup=1)
        assert result.success is True

    def test_vision_preprocess_throughput_positive(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.VISION_PREPROCESS, iterations=3, warmup=1)
        assert result.throughput > 0.0

    def test_reasoning_slm_workload_succeeds(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.REASONING_SLM, iterations=5, warmup=1)
        assert result.success is True

    def test_reasoning_slm_throughput_gt_1000(self, fresh_engine):
        """Pure symbolic reasoning must be very fast (>1000 ops/sec)."""
        result = fresh_engine.run_benchmark(WorkloadType.REASONING_SLM, iterations=10, warmup=2)
        assert result.throughput > 1000.0, (
            f"Symbolic reasoning too slow: {result.throughput:.1f} ops/sec"
        )

    def test_ocr_workload_has_result(self, fresh_engine):
        """OCR may succeed or report unavailability - must not crash."""
        result = fresh_engine.run_benchmark(WorkloadType.OCR, iterations=2, warmup=1)
        assert result is not None
        assert isinstance(result, BenchmarkResult)

    def test_ocr_workload_has_provider_name(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.OCR, iterations=1, warmup=0)
        assert result.provider and len(result.provider) > 0

    def test_all_workloads_run_without_exception(self, fresh_engine):
        for wl in WorkloadType:
            result = fresh_engine.run_benchmark(wl, iterations=2, warmup=1)
            assert result is not None, f"run_benchmark({wl}) returned None"

    def test_workload_result_device_nonempty(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=2, warmup=1)
        assert result.device and len(result.device) > 0

    def test_workload_result_runtime_nonempty(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=2, warmup=1)
        assert result.runtime and len(result.runtime) > 0

    def test_workload_first_latency_positive(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=3, warmup=1)
        assert result.first_latency_ms > 0.0

    def test_workload_memory_before_positive(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=2, warmup=1)
        assert result.memory_before_mb > 0.0


# ──────────────────────────────────────────────────────────────────────────────
# 6. Truthfulness Invariants
# ──────────────────────────────────────────────────────────────────────────────

class TestTruthfulnessInvariants:
    def test_benchmark_success_false_when_provider_unavailable(self, fresh_engine):
        """If provider is unavailable, result.success must be False."""
        with patch.object(
            fresh_engine._selector,
            "select_provider",
            return_value=RuntimeProviderInfo(
                provider_id="fake_npu",
                display_name="Fake NPU",
                device_type=DeviceType.NPU,
                vendor="Qualcomm",
                available=False,
                failure_reason="Not installed",
            ),
        ):
            result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=2, warmup=1)
            assert result.success is False
            assert result.error is not None

    def test_cpu_result_not_labeled_as_npu(self, fresh_engine):
        """CPU execution result runtime label must not contain 'NPU'."""
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=3, warmup=1)
        if result.success:
            assert "NPU" not in result.runtime.upper(), (
                f"CPU execution was mislabeled as NPU: {result.runtime}"
            )

    def test_latency_values_positive_when_successful(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=3, warmup=1)
        if result.success:
            assert result.average_latency_ms > 0.0
            assert result.p50_latency_ms > 0.0
            assert result.p95_latency_ms > 0.0

    def test_run_benchmark_does_not_auto_start(self):
        """BenchmarkEngine must NEVER run benchmarks on import/init."""
        engine = BenchmarkEngine()
        assert len(engine.get_history()) == 0, (
            "BenchmarkEngine must not auto-run benchmarks on instantiation"
        )

    def test_truthfulness_metadata_in_result(self, fresh_engine):
        result = fresh_engine.run_benchmark(WorkloadType.SYNTHETIC_BENCHMARK, iterations=2, warmup=1)
        d = result.to_dict()
        assert "authentic" in str(d).lower() or result.success is True
