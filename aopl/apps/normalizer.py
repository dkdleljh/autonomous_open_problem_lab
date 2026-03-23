from __future__ import annotations

from pathlib import Path

from aopl.core.io_utils import ensure_dir, write_json
from aopl.core.types import NormalizedProblem, ProblemRecord


class Normalizer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.out_dir = ensure_dir(root / "data" / "normalized")

    def normalize(self, problem: ProblemRecord) -> NormalizedProblem:
        objects: list[str] = []
        text_bundle = " ".join(problem.assumptions + [problem.statement, problem.goal]).lower()
        if "그래프" in text_bundle:
            objects.extend(["유한 단순 그래프", "꼭짓점", "간선"])
        if "정수" in text_bundle:
            objects.extend(["정수", "합동류"])
        if not objects:
            objects.append("일반 수학 객체")

        equivalent_forms = [
            f"{problem.goal}와 동치로 표현되는 최소 조건형",
            f"{problem.goal}의 반례 부재형",
        ]
        weak_forms = [
            f"{problem.goal}에서 탐색 범위를 제한한 약화형",
            f"{problem.goal}에서 조건 일부를 제거한 약화형",
        ]
        strong_forms = [
            f"{problem.goal}에 추가 제약을 포함한 강한형",
        ]

        notation_map = {
            "G": "그래프",
            "V(G)": "꼭짓점 집합",
            "E(G)": "간선 집합",
            "n": "자연수 인덱스",
        }

        normalized = NormalizedProblem(
            problem_id=problem.problem_id,
            title=problem.title,
            domain=problem.domain,
            objects=objects,
            assumptions=problem.assumptions,
            target=problem.goal,
            equivalent_forms=equivalent_forms,
            weak_forms=weak_forms,
            strong_forms=strong_forms,
            notation_map=notation_map,
            source_problem=problem.to_dict(),
        )

        write_json(self.out_dir / f"{problem.problem_id}_normalized.json", normalized.to_dict())
        return normalized
