from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.submission_builder import SubmissionBuilder
from aopl.core.types import FormalizationReport, PaperManifest, VerificationReport


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_checksum_file_created(tmp_path):
    project_root = prepare_project_root(tmp_path)
    ko = project_root / "papers" / "ko" / "prob_checksum.tex"
    en = project_root / "papers" / "en" / "prob_checksum.tex"
    bib = project_root / "papers" / "shared" / "prob_checksum.bib"
    appendix = project_root / "papers" / "shared" / "prob_checksum_appendix.md"
    pdf = project_root / "papers" / "builds" / "prob_checksum.pdf"
    manifest_file = project_root / "papers" / "builds" / "prob_checksum_paper_manifest.json"

    for path, content in [
        (ko, "ko"),
        (en, "en"),
        (bib, "bib"),
        (appendix, "appendix"),
        (pdf, "pdf"),
        (manifest_file, "{}"),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if path.suffix == ".pdf" else "w"
        with path.open(mode) as file:
            if mode == "wb":
                file.write(b"%PDF-1.4\n%%EOF\n")
            else:
                file.write(content)

    paper_manifest = PaperManifest(
        problem_id="prob_checksum",
        backend="demo",
        theorem_numbers=["정리 1"],
        equation_numbers=["(1)"],
        reference_keys=["ref1"],
        ko_tex=str(ko.relative_to(project_root)),
        en_tex=str(en.relative_to(project_root)),
        bib_file=str(bib.relative_to(project_root)),
        appendix_file=str(appendix.relative_to(project_root)),
        pdf_file=str(pdf.relative_to(project_root)),
        pdf_build_attempted=True,
        pdf_build_success=True,
        pdf_artifact_kind="latex_build",
    )
    verification = VerificationReport(
        problem_id="prob_checksum",
        backend_summary={"proof": "demo", "counterexample": "demo"},
        passed=True,
        critical_issues=[],
        warnings=["demo backend 사용"],
        counterexample_report={},
        gate_reason="ok",
    )
    formal_report = FormalizationReport(
        problem_id="prob_checksum",
        backend="demo",
        lean_file="formal/generated_skeletons/prob_checksum.lean",
        imports=["Mathlib"],
        obligations_total=1,
        obligations_resolved=0,
        obligations_unresolved=["ob1"],
        build_attempted=False,
        build_success=False,
        build_log_file="formal/proof_obligations/prob_checksum.log",
        artifact_kind="skeleton_only",
    )

    submission = SubmissionBuilder(project_root).build(
        paper_manifest, verification, formal_report
    )
    checksum_path = project_root / submission.checksum_file

    assert checksum_path.exists()
    lines = checksum_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    assert submission.verification_summary["warning_count"] == 1
    assert submission.artifact_summary["formalization_artifact_kind"] == "skeleton_only"
