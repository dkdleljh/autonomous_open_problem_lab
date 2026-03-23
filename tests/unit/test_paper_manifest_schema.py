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


def assert_paper_manifest_schema(payload: dict[str, object]) -> None:
    for key in [
        "problem_id",
        "backend",
        "theorem_numbers",
        "equation_numbers",
        "reference_keys",
        "ko_tex",
        "en_tex",
        "bib_file",
        "appendix_file",
        "pdf_file",
        "pdf_build_attempted",
        "pdf_build_success",
        "pdf_artifact_kind",
    ]:
        assert key in payload


def test_paper_manifest_schema_validation(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_manifest",
        title="manifest schema test",
        domain="graph_theory",
        statement="statement",
        assumptions=["a"],
        goal="goal",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
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
            ProofNode("n0", "definition", "d", "d", [], "ready"),
            ProofNode("n1", "theorem", "t", "t", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )
    verification = VerificationReport(
        record.problem_id,
        {"proof": "demo", "counterexample": "demo"},
        True,
        [],
        [],
        {},
        "ok",
    )
    formal = FormalizationReport(
        record.problem_id, "demo", "x.lean", ["Mathlib"], 1, 0, ["o"], False, False, "x.log", "skeleton_only"
    )
    manifest = PaperGenerator(project_root).generate(normalized, dag, verification, formal)
    assert_paper_manifest_schema(manifest.to_dict())
