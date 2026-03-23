from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.orchestrator import Orchestrator


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_release_package_regression(tmp_path):
    project_root = prepare_project_root(tmp_path)
    summary = Orchestrator(project_root).run(limit=1)
    assert summary["processed"]

    item = summary["processed"][0]
    submission_manifest = item["submission_manifest"]
    package_path = project_root / submission_manifest["package_file"]
    source_bundle_path = project_root / submission_manifest["source_bundle_file"]
    checksum_path = project_root / submission_manifest["checksum_file"]

    assert package_path.exists()
    assert source_bundle_path.exists()
    assert checksum_path.exists()
