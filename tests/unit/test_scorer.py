from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.apps.scorer import Scorer
from aopl.core.types import PipelineStage, ProblemRecord


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_score_calculation(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_score_case",
        title="점수 계산 테스트",
        domain="number_theory",
        statement="정수 조건의 점수화를 확인한다.",
        assumptions=["정수 연산을 사용한다."],
        goal="약화형 분해 가능성을 점검한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "survey", "reliability": 0.92}
        ],
        status=PipelineStage.REGISTERED,
    )

    normalized = Normalizer(project_root).normalize(record)
    score = Scorer(project_root).score(normalized)

    assert 0 <= score.score <= 1
    assert score.formalizability > 0
    assert score.decomposability > 0
