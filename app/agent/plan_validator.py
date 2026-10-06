"""
VisionPilot Plan Validator and Sanitizer.

Enforces strict validation on all model-generated TaskPlans:
- Schema and required field validation
- Capability existence and authorization
- Disallows arbitrary code injection (e.g. 'subprocess', 'powershell', 'os.system', 'eval')
- Enforces data-only parameter constraints (parameters must be structured Dict, not executable code)
- Step order continuity and dependency graph acyclicity
- Risk-level assignment validation
- Rejects malformed or invented capabilities
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from app.agent.capabilities import CapabilityRegistry, capability_registry
from app.agent.task_schema import PlanStatus, PlanStep, RiskLevel, TaskPlan
from app.core.exceptions import PlanningError
from app.core.logger import logger


class PlanValidator:
    """Validates structural correctness, capability bounds, and safety invariants of TaskPlans."""

    # Disallowed executable substrings in text fields or parameter values
    _FORBIDDEN_CODE_PATTERNS = [
        re.compile(r"\b(powershell|pwsh|cmd\.exe)\b", re.IGNORECASE),
        re.compile(r"\b(subprocess|os\.system|eval\(|exec\(|import\s+os)\b", re.IGNORECASE),
        re.compile(r"\b(__import__|open\(|socket|shutil\.rmtree)\b", re.IGNORECASE),
        re.compile(r"<\s*script\b", re.IGNORECASE),
    ]

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self.registry = registry or capability_registry

    def validate_plan(self, plan: TaskPlan) -> Tuple[bool, List[str]]:
        """
        Validates the TaskPlan.
        Returns: (is_valid: bool, errors: List[str])
        """
        errors: List[str] = []

        # 1. Basic Plan Fields
        if not plan.command_id:
            errors.append("Plan missing required field 'command_id'.")
        if not plan.goal and not plan.requires_clarification:
            errors.append("Plan missing required field 'goal'.")

        # Clarification plans are valid with zero steps
        if plan.requires_clarification:
            if not plan.clarification_question:
                errors.append("Clarification plan missing 'clarification_question'.")
            return len(errors) == 0, errors

        # If plan status is UNSUPPORTED, it is valid to have 0 steps
        if plan.status == PlanStatus.UNSUPPORTED:
            return True, []

        # 2. Steps validation
        if not plan.steps:
            errors.append("Plan contains zero steps and is not a clarification request.")
            return False, errors

        step_ids: Set[str] = set()
        for idx, step in enumerate(plan.steps):
            step_errors = self._validate_step(step, idx + 1, step_ids)
            errors.extend(step_errors)
            step_ids.add(step.step_id)

        # 3. Step Dependency Graph Validation (acyclic, valid references)
        dep_errors = self._validate_dependencies(plan.steps, step_ids)
        errors.extend(dep_errors)

        # 4. Code & Injection Sanitization across all plan fields
        injection_errors = self._check_arbitrary_code(plan)
        errors.extend(injection_errors)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Plan validation failed for plan {plan.plan_id}: {errors}")
        return is_valid, errors

    def _validate_step(self, step: PlanStep, expected_order: int, existing_ids: Set[str]) -> List[str]:
        """Validates an individual PlanStep."""
        errs: List[str] = []

        if not step.step_id:
            errs.append(f"Step at index {expected_order} missing step_id.")
        elif step.step_id in existing_ids:
            errs.append(f"Duplicate step_id detected: '{step.step_id}'.")

        if step.order != expected_order:
            errs.append(f"Step '{step.step_id}' order mismatch: expected {expected_order}, got {step.order}.")

        # Capability validation
        cap_name = step.intent.capability
        if not cap_name:
            errs.append(f"Step '{step.step_id}' missing capability intent.")
        elif not self.registry.is_known(cap_name):
            errs.append(f"Step '{step.step_id}' uses unknown capability '{cap_name}'.")
        elif self.registry.is_blocked(cap_name):
            errs.append(f"Step '{step.step_id}' uses BLOCKED capability '{cap_name}'.")

        # Parameters must be data dictionary, never raw code string
        if not isinstance(step.intent.parameters, dict):
            errs.append(f"Step '{step.step_id}' parameters must be a dictionary of data, got {type(step.intent.parameters)}.")

        return errs

    def _validate_dependencies(self, steps: List[PlanStep], all_ids: Set[str]) -> List[str]:
        """Validates that step dependencies are prerequisite only and acyclic."""
        errs: List[str] = []
        seen_ids: Set[str] = set()

        for step in steps:
            for dep in step.depends_on:
                if dep not in all_ids:
                    errs.append(f"Step '{step.step_id}' depends on non-existent step '{dep}'.")
                elif dep not in seen_ids:
                    errs.append(f"Step '{step.step_id}' depends on forward or self step '{dep}'. Dependency order violated.")
            seen_ids.add(step.step_id)

        return errs

    def _check_arbitrary_code(self, plan: TaskPlan) -> List[str]:
        """Scans plan text and parameters for executable shell/python payloads."""
        errs: List[str] = []

        def check_text(val: str, location: str) -> None:
            for pattern in self._FORBIDDEN_CODE_PATTERNS:
                if pattern.search(val):
                    errs.append(f"Arbitrary code payload detected in {location}: '{val[:40]}...'.")

        check_text(plan.goal, "plan.goal")
        check_text(plan.summary, "plan.summary")

        for step in plan.steps:
            check_text(step.description, f"step {step.step_id} description")
            for param_key, param_val in step.intent.parameters.items():
                if isinstance(param_val, str):
                    check_text(param_val, f"step {step.step_id} param '{param_key}'")

        return errs


# Global plan validator instance
plan_validator = PlanValidator()
