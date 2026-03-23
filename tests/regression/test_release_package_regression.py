from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.orchestrator import Orchestrator
from aopl.core.io_utils import read_yaml, write_yaml


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_release_package_regression(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime_config = read_yaml(runtime_file, default={})
    runtime_config["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime_config)

    summary = Orchestrator(project_root).run(limit=1)
    assert summary["processed"]

    item = summary["processed"][0]
    submission_manifest = item["submission_manifest"]
    package_path = project_root / submission_manifest["package_file"]
    source_bundle_path = project_root / submission_manifest["source_bundle_file"]
    checksum_path = project_root / submission_manifest["checksum_file"]
    release_notes_path = project_root / submission_manifest["release_notes_file"]

    assert package_path.exists()
    assert source_bundle_path.exists()
    assert checksum_path.exists()
    assert release_notes_path.exists()
    notes = release_notes_path.read_text(encoding="utf-8")
    assert "검증 중대 이슈 수:" in notes
    assert "검증 경고 수:" in notes
    assert "형식화 아티팩트 유형:" in notes
    assert summary["stats"]["processed_count"] >= 1
    assert summary["stats"]["released_problem_ids"]
    assert "verification_summary" in item
    assert "provenance_summary" in item
    assert item["provenance_summary"]["harvest_batch_id"]
    assert item["provenance_summary"]["source_signature"]
