from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.apps.paper_generator import PaperGenerator
from aopl.core.types import (
    FormalizationReport,
    PipelineStage,
    ProblemRecord,
    ProofDAG,
    ProofNode,
    VerificationReport,
)


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_paper_number_sync(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_paper_sync",
        title="논문 번호 동기화 테스트",
        domain="graph_theory",
        statement="번호 동기화를 확인한다.",
        assumptions=["유한 그래프를 사용한다."],
        goal="정리 번호를 일치시킨다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)
    dag = ProofDAG(
        problem_id=record.problem_id,
        root_node="n0",
        target_node="n1",
        nodes=[
            ProofNode("n0", "definition", "정의", "정의", [], "ready"),
            ProofNode("n1", "theorem", "정리", "정리 서술", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )
    verification = VerificationReport(
        problem_id=record.problem_id,
        passed=True,
        critical_issues=[],
        warnings=[],
        counterexample_report={},
        gate_reason="ok",
    )
    formal_report = FormalizationReport(
        problem_id=record.problem_id,
        lean_file="formal/generated_skeletons/x.lean",
        imports=["Mathlib"],
        obligations_total=1,
        obligations_resolved=0,
        obligations_unresolved=["ob1"],
        build_attempted=False,
        build_success=False,
        build_log_file="formal/proof_obligations/x.log",
    )

    generator = PaperGenerator(project_root)
    manifest = generator.generate(normalized, dag, verification, formal_report)
    passed, reason = generator.qa_check(manifest)

    assert passed is True, reason
