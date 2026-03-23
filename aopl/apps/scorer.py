from __future__ import annotations

from pathlib import Path

from aopl.core.io_utils import ensure_dir, read_yaml, write_json
from aopl.core.types import NormalizedProblem, ScoreCard

DEFAULT_WEIGHTS = {
    "formalizability": 0.30,
    "decomposability": 0.25,
    "library_fit": 0.20,
    "counterexample_searchability": 0.15,
    "paperability": 0.10,
}


class Scorer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.out_dir = ensure_dir(root / "data" / "normalized")
        self.config_file = root / "configs" / "scoring" / "default.yaml"

    def _weights(self) -> dict[str, float]:
        loaded = read_yaml(self.config_file, default={})
        if not isinstance(loaded, dict):
            return dict(DEFAULT_WEIGHTS)
        weights = dict(DEFAULT_WEIGHTS)
        for key in DEFAULT_WEIGHTS:
            value = (
                loaded.get("weights", {}).get(key)
                if isinstance(loaded.get("weights"), dict)
                else None
            )
            if isinstance(value, (int, float)):
                weights[key] = float(value)
        return weights

    def _formalizability(self, problem: NormalizedProblem) -> float:
        base = 0.55
        if problem.domain in {"graph_theory", "number_theory", "combinatorics"}:
            base += 0.25
        if len(problem.assumptions) <= 4:
            base += 0.10
        if len(problem.notation_map) >= 3:
            base += 0.10
        return min(base, 0.99)

    def _decomposability(self, problem: NormalizedProblem) -> float:
        base = 0.45
        if len(problem.weak_forms) >= 2:
            base += 0.25
        if len(problem.equivalent_forms) >= 2:
            base += 0.20
        if len(problem.assumptions) <= 5:
            base += 0.10
        return min(base, 0.98)

    def _library_fit(self, problem: NormalizedProblem) -> float:
        tags_text = " ".join(problem.objects + problem.assumptions + [problem.target])
        score = 0.40
        if "그래프" in tags_text:
            score += 0.25
        if "정수" in tags_text or "합동" in tags_text:
            score += 0.25
        if "유한" in tags_text:
            score += 0.10
        return min(score, 0.97)

    def _counterexample_searchability(self, problem: NormalizedProblem) -> float:
        score = 0.40
        if "유한" in " ".join(problem.objects):
            score += 0.20
        if problem.domain in {"graph_theory", "combinatorics"}:
            score += 0.25
        if "범위" in " ".join(problem.weak_forms):
            score += 0.10
        return min(score, 0.95)

    def _paperability(self, problem: NormalizedProblem) -> float:
        score = 0.50
        if len(problem.source_problem.get("sources", [])) >= 1:
            score += 0.20
        if len(problem.equivalent_forms) >= 1 and len(problem.weak_forms) >= 1:
            score += 0.20
        return min(score, 0.95)

    def score(self, normalized_problem: NormalizedProblem) -> ScoreCard:
        weights = self._weights()
        formalizability = self._formalizability(normalized_problem)
        decomposability = self._decomposability(normalized_problem)
        library_fit = self._library_fit(normalized_problem)
        counterexample_searchability = self._counterexample_searchability(normalized_problem)
        paperability = self._paperability(normalized_problem)
        total = (
            weights["formalizability"] * formalizability
            + weights["decomposability"] * decomposability
            + weights["library_fit"] * library_fit
            + weights["counterexample_searchability"] * counterexample_searchability
            + weights["paperability"] * paperability
        )

        rationale = [
            "형식화 대상 영역 적합성 점수를 우선 반영함",
            "약화형과 동치형 자동 생성 가능성을 반영함",
            "반례 탐색 가능성과 논문화 준비도를 함께 계산함",
        ]
        card = ScoreCard(
            problem_id=normalized_problem.problem_id,
            formalizability=round(formalizability, 4),
            decomposability=round(decomposability, 4),
            library_fit=round(library_fit, 4),
            counterexample_searchability=round(counterexample_searchability, 4),
            paperability=round(paperability, 4),
            score=round(total, 4),
            selected=total >= 0.55,
            rationale=rationale,
        )
        write_json(self.out_dir / f"{normalized_problem.problem_id}_score.json", card.to_dict())
        return card
