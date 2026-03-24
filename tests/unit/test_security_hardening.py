from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from aopl.apps.formalizer import Formalizer
from aopl.apps.paper_generator import PaperGenerator
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.core.gates import GatePolicy
from aopl.core.types import (
    FormalizationReport,
    NormalizedProblem,
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


def test_submission_builder_rejects_outside_project_paths(tmp_path):
    project_root = prepare_project_root(tmp_path)
    manifest = PaperManifest(
        problem_id="prob_escape",
        backend="demo",
        theorem_numbers=["정리 1"],
        equation_numbers=["(1)"],
        reference_keys=["ref1"],
        ko_tex="../outside.tex",
        en_tex="papers/en/prob_escape.tex",
        bib_file="papers/shared/prob_escape.bib",
        appendix_file="papers/shared/prob_escape_appendix.md",
        pdf_file="papers/builds/prob_escape.pdf",
        pdf_build_attempted=True,
        pdf_build_success=True,
        pdf_artifact_kind="latex_build",
    )

    with pytest.raises(ValueError):
        SubmissionBuilder(project_root).build(manifest)


def test_release_gate_rejects_absolute_submission_paths(tmp_path):
    project_root = prepare_project_root(tmp_path)
    outside_file = tmp_path / "outside.zip"
    outside_file.write_text("payload", encoding="utf-8")

    passed, reason = GatePolicy(project_root).release(
        {
            "package_file": str(outside_file),
            "source_bundle_file": "data/paper_assets/releases/source.tar.gz",
            "checksum_file": "data/paper_assets/releases/checksums.txt",
            "release_notes_file": "data/paper_assets/releases/release_notes.md",
        },
        {"pdf_build_success": True, "pdf_artifact_kind": "latex_build"},
        {},
        {"passed": True},
        {"build_success": True, "obligations_unresolved": []},
    )

    assert passed is False
    assert "프로젝트 범위" in reason


def test_paper_generator_escapes_latex_special_characters(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_tex_escape",
        title=r"title_%_#_{bad}",
        domain="graph_theory",
        statement="statement",
        assumptions=["a"],
        goal=r"goal with # and % and _ and {braces}",
        aliases=[],
        sources=[
            {
                "name": r"src_%_{name}",
                "url": "https://example.org/ref{1}",
                "type": "registry",
                "reliability": 0.9,
            }
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = NormalizedProblem(
        problem_id=record.problem_id,
        title=record.title,
        domain=record.domain,
        objects=["graph"],
        assumptions=record.assumptions,
        target=record.goal,
        equivalent_forms=[],
        weak_forms=[],
        strong_forms=[],
        notation_map={},
        source_problem=record.to_dict(),
    )
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
        1,
        [],
        False,
        False,
        "x.log",
        "skeleton_only",
    )

    manifest = PaperGenerator(project_root).generate(normalized, dag, verification, formal)
    ko_text = (project_root / manifest.ko_tex).read_text(encoding="utf-8")
    bib_text = (project_root / manifest.bib_file).read_text(encoding="utf-8")

    assert r"title\_\%\_\#\_\{bad\}" in ko_text
    assert r"goal with \# and \% and \_ and \{braces\}" in ko_text
    assert r"src\_\%\_\{name\}" in bib_text
    assert r"\url{https://example.org/ref%7B1%7D}" in bib_text


def test_formalizer_handles_timeout_gracefully(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    problem = NormalizedProblem(
        problem_id="prob_timeout",
        title="timeout",
        domain="graph_theory",
        objects=["graph"],
        assumptions=["finite"],
        target="goal",
        equivalent_forms=[],
        weak_forms=[],
        strong_forms=[],
        notation_map={},
        source_problem={},
    )
    dag = ProofDAG(
        problem_id=problem.problem_id,
        backend="demo",
        root_node="n0",
        target_node="n1",
        nodes=[
            ProofNode("n0", "definition", "d", "d", [], "ready"),
            ProofNode("n1", "theorem", "t", "t", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/fake")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="lean", timeout=kwargs["timeout"])

    monkeypatch.setattr("subprocess.run", fake_run)

    report = Formalizer(project_root).generate(problem, dag)
    log_text = (project_root / report.build_log_file).read_text(encoding="utf-8")

    assert report.build_attempted is True
    assert report.build_success is False
    assert "초과" in log_text
