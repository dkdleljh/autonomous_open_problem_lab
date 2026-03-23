from __future__ import annotations

from pathlib import Path

from aopl.core.config_store import ConfigStore
from aopl.core.io_utils import ensure_dir, write_json
from aopl.core.schema_utils import validate_schema
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
        self.config_store = ConfigStore(root)

    def _weights(self) -> dict[str, float]:
        loaded = self.config_store.scoring()
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

    def _selection_threshold(self) -> float:
        loaded = self.config_store.scoring()
        if not isinstance(loaded, dict):
            return 0.55
        selection = loaded.get("selection", {})
        if isinstance(selection, dict):
            value = selection.get("min_score")
            if isinstance(value, (int, float)):
                return float(value)
        return 0.55

    def _domain_config(self, problem: NormalizedProblem) -> dict[str, object]:
        loaded = self.config_store.problem_domain(problem.domain)
        return loaded if isinstance(loaded, dict) else {}

    def _domain_priority_multiplier(self, problem: NormalizedProblem) -> float:
        config = self._domain_config(problem)
        enabled = config.get("enabled", True)
        if isinstance(enabled, bool) and not enabled:
            return 0.0
        priority_boost = config.get("priority_boost", 1.0)
        if isinstance(priority_boost, (int, float)) and priority_boost > 0:
            return float(priority_boost)
        return 1.0

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
        selection_threshold = self._selection_threshold()
        priority_multiplier = self._domain_priority_multiplier(normalized_problem)
        formalizability = self._formalizability(normalized_problem)
        decomposability = self._decomposability(normalized_problem)
        library_fit = self._library_fit(normalized_problem)
        counterexample_searchability = self._counterexample_searchability(normalized_problem)
        paperability = self._paperability(normalized_problem)
        base_total = (
            weights["formalizability"] * formalizability
            + weights["decomposability"] * decomposability
            + weights["library_fit"] * library_fit
            + weights["counterexample_searchability"] * counterexample_searchability
            + weights["paperability"] * paperability
        )
        total = min(base_total * priority_multiplier, 0.999)

        rationale = [
            "형식화 대상 영역 적합성 점수를 우선 반영함",
            "약화형과 동치형 자동 생성 가능성을 반영함",
            "반례 탐색 가능성과 논문화 준비도를 함께 계산함",
        ]
        if priority_multiplier == 0.0:
            rationale.append("도메인 설정에서 비활성화되어 자동 선별 대상에서 제외됨")
        elif priority_multiplier != 1.0:
            rationale.append(
                f"도메인 우선순위 배수 {priority_multiplier:.2f} 를 최종 점수에 반영함"
            )
        card = ScoreCard(
            problem_id=normalized_problem.problem_id,
            formalizability=round(formalizability, 4),
            decomposability=round(decomposability, 4),
            library_fit=round(library_fit, 4),
            counterexample_searchability=round(counterexample_searchability, 4),
            paperability=round(paperability, 4),
            score=round(total, 4),
            selected=total >= selection_threshold,
            rationale=rationale,
        )
        validate_schema(self.root, "score_card_schema", card.to_dict())
        write_json(self.out_dir / f"{normalized_problem.problem_id}_score.json", card.to_dict())
        return card
