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
        backend="demo",
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
        backend="demo",
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
    assert report.backend_summary["proof"] == "demo"
    assert report.backend_summary["counterexample"] == "demo"
    assert any("금지 표현" in item for item in report.critical_issues)


def test_verifier_blocks_when_weak_variant_is_missing_from_proof_dag(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_verify_counterexample_mismatch",
        title="반례-증명 불일치 테스트",
        domain="number_theory",
        statement="정수 구조 검증을 테스트한다.",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
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
        backend="real",
        root_node="n0",
        target_node="n2",
        nodes=[
            ProofNode("n0", "definition", "정의", "기본 정의", [], "ready"),
            ProofNode("n1", "lemma", "보조정리", "일반 환원만 수행한다.", ["n0"], "candidate"),
            ProofNode("n2", "theorem", "주정리", "목표를 보인다.", ["n1"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}, {"from": "n1", "to": "n2"}],
    )
    counterexample_report = CounterexampleReport(
        problem_id=record.problem_id,
        backend="real",
        checked_variant="strong_variant",
        found_counterexample=True,
        counterexample={"n": 4},
        explored_bound=24,
        seed=1,
        elapsed_seconds=0.1,
        weak_variant_recommendation="n을 홀수로 제한한다.",
    )

    report = Verifier(project_root).verify(normalized, dag, counterexample_report)

    assert report.passed is False
    assert any("약화형 권고" in item for item in report.critical_issues)


def test_verifier_warns_when_search_bound_is_absent_from_proof_dag(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_verify_bound_warning",
        title="탐색 상한 경고 테스트",
        domain="number_theory",
        statement="정수 구조 검증을 테스트한다.",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
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
        backend="real",
        root_node="n0",
        target_node="n2",
        nodes=[
            ProofNode("n0", "definition", "정의", "기본 정의", [], "ready"),
            ProofNode("n1", "lemma", "약화형 환원 경로", "n을 홀수로 제한한다.", ["n0"], "candidate"),
            ProofNode("n2", "theorem", "주정리", "목표를 보인다.", ["n1"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}, {"from": "n1", "to": "n2"}],
    )
    counterexample_report = CounterexampleReport(
        problem_id=record.problem_id,
        backend="real",
        checked_variant="strong_variant",
        found_counterexample=True,
        counterexample={"n": 4},
        explored_bound=24,
        seed=1,
        elapsed_seconds=0.1,
        weak_variant_recommendation="n을 홀수로 제한한다.",
    )

    report = Verifier(project_root).verify(normalized, dag, counterexample_report)

    assert report.passed is True
    assert any("탐색 상한 정보" in item for item in report.warnings)
