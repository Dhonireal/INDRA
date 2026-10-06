import sys
import os
from pathlib import Path
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    print("Step 1: Starting test_bench.py")
    from app.hardware.benchmark_engine import benchmark_engine, WorkloadType
    print("Step 2: Calling run_benchmark(WorkloadType.OCR, iterations=2, warmup=1)")
    res = benchmark_engine.run_benchmark(WorkloadType.OCR, iterations=2, warmup=1)
    print("Step 3: Benchmark completed successfully:")
    print("  Success:", res.success)
    print("  Average:", res.average_latency_ms, "ms")
    print("  P50:    ", res.p50_latency_ms, "ms")
    print("  P95:    ", res.p95_latency_ms, "ms")
    print("  Rate:   ", res.throughput, "ops/sec")
    print("  Error:  ", res.error)
except Exception as e:
    print("EXCEPTION OCCURRED:", e)
    traceback.print_exc()
