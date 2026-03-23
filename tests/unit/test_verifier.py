from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.apps.verifier import Verifier
from aopl.core.types import CounterexampleReport, PipelineStage, ProblemRecord, ProofDAG, ProofNode


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_verifier_detects_logical_gap_phrase(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_verify_gap",
        title="검증 공백 테스트",
        domain="combinatorics",
        statement="조합 구조 검증을 테스트한다.",
        assumptions=["유한 집합을 사용한다."],
        goal="핵심 조건을 만족함을 보인다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "survey", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)

    dag = ProofDAG(
        problem_id=record.problem_id,
        root_node="n0",
        target_node="n1",
        nodes=[
            ProofNode("n0", "definition", "정의", "기본 정의", [], "ready"),
            ProofNode("n1", "theorem", "주정리", "이 단계는 자명하다", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )
    counterexample_report = CounterexampleReport(
        problem_id=record.problem_id,
        checked_variant="strong_variant",
        found_counterexample=False,
        counterexample=None,
        explored_bound=10,
        seed=1,
        elapsed_seconds=0.1,
        weak_variant_recommendation=None,
    )

    report = Verifier(project_root).verify(normalized, dag, counterexample_report)
    assert report.passed is False
    assert any("금지 표현" in item for item in report.critical_issues)
