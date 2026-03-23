from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aopl.apps.normalizer import Normalizer
from aopl.apps.orchestrator import Orchestrator
from aopl.apps.paper_generator import PaperGenerator
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.core.io_utils import read_json, read_yaml, write_yaml
from aopl.core.schema_utils import validate_schema
from aopl.core.types import (
    FormalizationReport,
    PaperManifest,
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


def test_validate_schema_rejects_invalid_proof_dag_backend(tmp_path):
    project_root = prepare_project_root(tmp_path)
    payload = {
        "problem_id": "prob_schema_runtime",
        "backend": "bad-backend",
        "root_node": "n0",
        "target_node": "n1",
        "nodes": [
            {
                "node_id": "n0",
                "node_type": "definition",
                "title": "d",
                "statement": "d",
                "dependencies": [],
                "status": "ready",
            },
            {
                "node_id": "n1",
                "node_type": "theorem",
                "title": "t",
                "statement": "t",
                "dependencies": ["n0"],
                "status": "draft",
            },
        ],
        "edges": [{"from": "n0", "to": "n1"}],
    }

    with pytest.raises(ValueError, match="proof_dag_schema"):
        validate_schema(project_root, "proof_dag_schema", payload)


def test_paper_generator_emits_schema_valid_manifest(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_schema_paper",
        title="schema paper test",
        domain="graph_theory",
        statement="statement long enough",
        assumptions=["a"],
        goal="goal text",
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
        record.problem_id,
        "demo",
        "x.lean",
        ["Mathlib"],
        1,
        0,
        ["o"],
        False,
        False,
        "x.log",
        "skeleton_only",
    )

    manifest = PaperGenerator(project_root).generate(normalized, dag, verification, formal)
    validate_schema(project_root, "paper_manifest_schema", manifest.to_dict())


def test_submission_builder_emits_schema_valid_manifest(tmp_path):
    project_root = prepare_project_root(tmp_path)
    paper_manifest = PaperManifest(
        problem_id="prob_schema_submission",
        backend="demo",
        theorem_numbers=["정리 1"],
        equation_numbers=["(1)"],
        reference_keys=["ref1"],
        ko_tex="papers/ko/prob_schema_submission.tex",
        en_tex="papers/en/prob_schema_submission.tex",
        bib_file="papers/shared/prob_schema_submission.bib",
        appendix_file="papers/shared/prob_schema_submission_appendix.md",
        pdf_file="papers/builds/prob_schema_submission.pdf",
        pdf_build_attempted=True,
        pdf_build_success=True,
        pdf_artifact_kind="latex_build",
    )
    for rel, content in [
        (paper_manifest.ko_tex, "ko"),
        (paper_manifest.en_tex, "en"),
        (paper_manifest.bib_file, "bib"),
        (paper_manifest.appendix_file, "appendix"),
    ]:
        path = project_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    pdf_path = project_root / paper_manifest.pdf_file
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    manifest_json = project_root / "papers" / "builds" / "prob_schema_submission_paper_manifest.json"
    manifest_json.parent.mkdir(parents=True, exist_ok=True)
    manifest_json.write_text("{}", encoding="utf-8")

    verification = VerificationReport(
        "prob_schema_submission",
        {"proof": "demo", "counterexample": "demo"},
        True,
        [],
        [],
        {},
        "ok",
    )
    formal = FormalizationReport(
        "prob_schema_submission",
        "demo",
        "formal/generated_skeletons/x.lean",
        ["Mathlib"],
        1,
        0,
        ["ob1"],
        False,
        False,
        "formal/proof_obligations/x.log",
        "skeleton_only",
    )

    submission = SubmissionBuilder(project_root).build(paper_manifest, verification, formal)
    validate_schema(project_root, "submission_manifest_schema", submission.to_dict())


def test_orchestrator_emits_schema_valid_run_summary(tmp_path):
    project_root = prepare_project_root(tmp_path)
    summary = Orchestrator(project_root).run(limit=1)
    validate_schema(project_root, "run_summary_schema", summary)


def test_verification_and_formalization_reports_are_schema_valid(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)
    summary = Orchestrator(project_root).run(limit=1)
    problem_id = summary["processed"][0]["problem_id"]
    verification_payload = read_json(
        project_root / "data" / "theorem_store" / f"{problem_id}_verification.json",
        default=None,
    )
    formal_payload = read_json(
        project_root / "formal" / "proof_obligations" / f"{problem_id}_formalization_report.json",
        default=None,
    )

    assert isinstance(verification_payload, dict)
    assert isinstance(formal_payload, dict)
    validate_schema(project_root, "verification_report_schema", verification_payload)
    validate_schema(project_root, "formalization_report_schema", formal_payload)


def test_counterexample_report_is_schema_valid(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)
    summary = Orchestrator(project_root).run(limit=1)
    problem_id = summary["processed"][0]["problem_id"]
    counterexample_payload = read_json(
        project_root / "data" / "experiments" / f"{problem_id}_counterexample.json",
        default=None,
    )

    assert isinstance(counterexample_payload, dict)
    validate_schema(project_root, "counterexample_report_schema", counterexample_payload)


def test_normalized_problem_and_score_card_are_schema_valid(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)
    summary = Orchestrator(project_root).run(limit=1)
    problem_id = summary["processed"][0]["problem_id"]
    normalized_payload = read_json(
        project_root / "data" / "normalized" / f"{problem_id}_normalized.json",
        default=None,
    )
    score_payload = read_json(
        project_root / "data" / "normalized" / f"{problem_id}_score.json",
        default=None,
    )

    assert isinstance(normalized_payload, dict)
    assert isinstance(score_payload, dict)
    validate_schema(project_root, "normalized_problem_schema", normalized_payload)
    validate_schema(project_root, "score_card_schema", score_payload)
