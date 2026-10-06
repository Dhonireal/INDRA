# Testing Architecture & Validation Guide — VisionPilot

## 1. Overview
VisionPilot maintains a strict, multi-tiered test infrastructure that guarantees safety, reliability, and correctness across desktop computer-use operations.

The test suite consists of:
- **Unit Tests (`tests/unit/`):** 229 tests validating individual components in isolation with mocks and deterministic fixtures.
- **Integration & E2E Workflows (`tests/integration/test_e2e_workflows.py`):** 6 tests validating multi-step autonomous execution, recovery, and UI thread responsiveness.
- **Security & Adversarial Tests (`tests/integration/test_security_adversarial.py`):** 27 tests validating prompt injection defense, untrusted data isolation, path traversal prevention, credential redaction, and SQL injection immunity.
- **System Benchmarks (`tests/integration/test_system_benchmarks.py`):** 4 tests computing rigorous statistical metrics ($N=20$) across Planner, Action Executor, Verifier, and History persistence.

Total tests: **266 tests, 100% passing**.

---

## 2. Running Tests

### Running the Entire Test Suite
```powershell
python -m pytest tests/ -v --tb=short
```

### Running Specific Test Suites
```powershell
# E2E Workflows
python -m pytest tests/integration/test_e2e_workflows.py -v

# Security and Adversarial Tests
python -m pytest tests/integration/test_security_adversarial.py -v

# Statistical Benchmarks
python -m pytest tests/integration/test_system_benchmarks.py -v
```

### Running UI Smoke Test
```powershell
python scripts/smoke_test_ui.py
```

---

## 3. Test Invariants & Principles

1. **Zero Mocking of Truth:**
   - Tests never use synthetic mocks to claim hardware acceleration (e.g. NPU active) when it is not verified.
   - Tests never mock the entire system and label it an E2E test.
2. **Independent Verification:**
   - Verifier assertions inspect actual filesystem state or real UI component status; they never accept `ActionResult.success = True` as proof of success.
3. **Safety Isolation:**
   - All filesystem operations are conducted within temporary directories (`tempfile.mkdtemp()`) configured in `PathSecurityPolicy`. Real user directories are never touched during automated testing.
4. **No Destructive Operations:**
   - Automated tests never permanently delete user files.
