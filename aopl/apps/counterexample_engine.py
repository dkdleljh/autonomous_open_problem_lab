from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from aopl.core.io_utils import ensure_dir, write_json
from aopl.core.types import CounterexampleReport, NormalizedProblem


class CounterexampleEngine:
    def __init__(self, root: Path, default_seed: int = 20260323) -> None:
        self.root = root
        self.default_seed = default_seed
        self.exp_dir = ensure_dir(root / "data" / "experiments")

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

        report = CounterexampleReport(
            problem_id=problem.problem_id,
            checked_variant="strong_variant",
            found_counterexample=found,
            counterexample=detail,
            explored_bound=bound,
            seed=self.default_seed,
            elapsed_seconds=round(elapsed, 6),
            weak_variant_recommendation=weak_recommend,
        )

        write_json(self.exp_dir / f"{problem.problem_id}_counterexample.json", report.to_dict())
        return report
