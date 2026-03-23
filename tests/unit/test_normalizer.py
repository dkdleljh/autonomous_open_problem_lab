from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.core.types import PipelineStage, ProblemRecord


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_problem_normalization(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_test_graph",
        title="테스트 그래프 문제",
        domain="graph_theory",
        statement="그래프의 조건을 테스트한다.",
        assumptions=["그래프는 유한하다."],
        goal="조건을 만족하는 구조의 존재성을 확인한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )

    normalized = Normalizer(project_root).normalize(record)

    assert normalized.problem_id == "prob_test_graph"
    assert normalized.assumptions
    assert normalized.target
    assert normalized.objects
    assert len(normalized.weak_forms) >= 1
