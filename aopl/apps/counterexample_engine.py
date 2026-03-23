from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from aopl.core.io_utils import ensure_dir, read_yaml, write_json
from aopl.core.schema_utils import validate_schema
from aopl.core.types import CounterexampleReport, NormalizedProblem


class CounterexampleEngine:
    def __init__(self, root: Path, default_seed: int = 20260323, backend: str = "demo") -> None:
        self.root = root
        self.default_seed = default_seed
        self.backend = backend
        self.exp_dir = ensure_dir(root / "data" / "experiments")

    def _write_report(
        self,
        problem: NormalizedProblem,
        found: bool,
        detail: dict[str, Any] | None,
        weak_recommend: str | None,
        bound: int,
        elapsed: float,
    ) -> CounterexampleReport:
        report = CounterexampleReport(
            problem_id=problem.problem_id,
            backend=self.backend,
            checked_variant="strong_variant",
            found_counterexample=found,
            counterexample=detail,
            explored_bound=bound,
            seed=self.default_seed,
            elapsed_seconds=round(elapsed, 6),
            weak_variant_recommendation=weak_recommend,
        )
        validate_schema(self.root, "counterexample_report_schema", report.to_dict())
        write_json(self.exp_dir / f"{problem.problem_id}_counterexample.json", report.to_dict())
        return report

    def _check_toy_rule(
        self, problem: NormalizedProblem, bound: int
    ) -> tuple[bool, dict[str, Any] | None, str | None]:
        toy_rule = str(
            problem.source_problem.get("metadata", {}).get("toy_counterexample_rule", "none")
        )
        if toy_rule == "strong_variant_false_small_n":
            for n in range(2, bound + 1):
                if n % 2 == 0:
                    counterexample = {
                        "n": n,
                        "reason": (
                            "강한형이 모든 자연수에서 성립한다고 두면 짝수 n에서 실패하는 샘플 규칙"
                        ),
                    }
                    return (
                        True,
                        counterexample,
                        "n을 홀수로 제한한 약화형을 권장: n >= 3, n % 2 = 1",
                    )
            return False, None, None
        return False, None, None

    def run(
        self, problem: NormalizedProblem, bound: int = 16, timeout_seconds: int = 20
    ) -> CounterexampleReport:
        start = time.time()
        random.seed(self.default_seed)
        found, detail, weak_recommend = self._check_toy_rule(problem, bound)

        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            raise TimeoutError("반례 탐색 시간이 예산을 초과하여 자동 중지되었습니다.")

        return self._write_report(problem, found, detail, weak_recommend, bound, elapsed)


class DemoCounterexampleEngine(CounterexampleEngine):
    def __init__(self, root: Path, default_seed: int = 20260323) -> None:
        super().__init__(root, default_seed=default_seed, backend="demo")


class RealCounterexampleEngine(CounterexampleEngine):
    def __init__(self, root: Path, default_seed: int = 20260323) -> None:
        super().__init__(root, default_seed=default_seed, backend="real")

    def _domain_default_bound(self, problem: NormalizedProblem, requested_bound: int) -> int:
        config_file = self.root / "configs" / "problems" / f"{problem.domain}.yaml"
        config = read_yaml(config_file, default={})
        if not isinstance(config, dict):
            return requested_bound
        default_bounds = config.get("default_search_bounds", {})
        if not isinstance(default_bounds, dict):
            return requested_bound
        preferred_keys = ["n_upper_bound", "max_vertices", "set_size_limit"]
        for key in preferred_keys:
            value = default_bounds.get(key)
            if isinstance(value, int) and value > 0:
                return min(requested_bound, value)
        return requested_bound

    def _integer_forbidden_residue_search(
        self, spec: dict[str, Any], bound: int
    ) -> tuple[bool, dict[str, Any] | None]:
        modulus = spec.get("modulus")
        residue = spec.get("forbidden_residue")
        start = spec.get("start", 1)
        if not isinstance(modulus, int) or modulus <= 0:
            raise ValueError("counterexample search spec의 modulus는 양의 정수여야 합니다.")
        if not isinstance(residue, int):
            raise ValueError("counterexample search spec의 forbidden_residue는 정수여야 합니다.")
        if not isinstance(start, int):
            raise ValueError("counterexample search spec의 start는 정수여야 합니다.")
        for n in range(max(start, 1), bound + 1):
            if n % modulus == residue % modulus:
                return True, {"n": n, "modulus": modulus, "residue": residue}
        return False, None

    def _integer_forbidden_values_search(
        self, spec: dict[str, Any], bound: int
    ) -> tuple[bool, dict[str, Any] | None]:
        values = spec.get("values", [])
        start = spec.get("start", 1)
        if not isinstance(values, list) or not all(isinstance(item, int) for item in values):
            raise ValueError("counterexample search spec의 values는 정수 리스트여야 합니다.")
        if not isinstance(start, int):
            raise ValueError("counterexample search spec의 start는 정수여야 합니다.")
        candidates = sorted({item for item in values if start <= item <= bound})
        if not candidates:
            return False, None
        n = candidates[0]
        return True, {"n": n, "values": candidates}

    def _integer_range_membership_search(
        self, spec: dict[str, Any], bound: int
    ) -> tuple[bool, dict[str, Any] | None]:
        start = spec.get("start", 1)
        interval_start = spec.get("interval_start")
        interval_end = spec.get("interval_end")
        if not isinstance(start, int):
            raise ValueError("counterexample search spec의 start는 정수여야 합니다.")
        if not isinstance(interval_start, int) or not isinstance(interval_end, int):
            raise ValueError(
                "counterexample search spec의 interval_start, interval_end는 정수여야 합니다."
            )
        if interval_start > interval_end:
            raise ValueError("counterexample search spec의 interval 범위가 올바르지 않습니다.")
        lower = max(start, interval_start)
        upper = min(bound, interval_end)
        if lower > upper:
            return False, None
        return True, {"n": lower, "interval": [interval_start, interval_end]}

    def run(
        self, problem: NormalizedProblem, bound: int = 16, timeout_seconds: int = 20
    ) -> CounterexampleReport:
        start = time.time()
        random.seed(self.default_seed)
        search_bound = self._domain_default_bound(problem, bound)
        metadata = problem.source_problem.get("metadata", {})
        spec = metadata.get("counterexample_search_spec", {}) if isinstance(metadata, dict) else {}
        if not isinstance(spec, dict):
            spec = {}

        found = False
        detail: dict[str, Any] | None = None
        weak_recommend = None
        search_type = spec.get("type")

        if search_type == "integer_forbidden_residue":
            found, detail = self._integer_forbidden_residue_search(spec, search_bound)
            if found:
                reason = spec.get("reason")
                if isinstance(reason, str) and reason.strip():
                    detail["reason"] = reason
                weak = spec.get("weak_variant_recommendation")
                if isinstance(weak, str) and weak.strip():
                    weak_recommend = weak
        elif search_type == "integer_forbidden_values":
            found, detail = self._integer_forbidden_values_search(spec, search_bound)
            if found:
                reason = spec.get("reason")
                if isinstance(reason, str) and reason.strip():
                    detail["reason"] = reason
                weak = spec.get("weak_variant_recommendation")
                if isinstance(weak, str) and weak.strip():
                    weak_recommend = weak
        elif search_type == "integer_range_membership":
            found, detail = self._integer_range_membership_search(spec, search_bound)
            if found:
                reason = spec.get("reason")
                if isinstance(reason, str) and reason.strip():
                    detail["reason"] = reason
                weak = spec.get("weak_variant_recommendation")
                if isinstance(weak, str) and weak.strip():
                    weak_recommend = weak

        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            raise TimeoutError("반례 탐색 시간이 예산을 초과하여 자동 중지되었습니다.")

        return self._write_report(
            problem,
            found,
            detail,
            weak_recommend,
            search_bound,
            elapsed,
        )
