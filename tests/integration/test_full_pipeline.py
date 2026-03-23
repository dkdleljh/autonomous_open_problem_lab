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


def test_full_pipeline_runs(tmp_path):
    project_root = prepare_project_root(tmp_path)
    summary = Orchestrator(project_root).run(limit=1)
    assert "processed" in summary
    assert "blocked" in summary
    assert len(summary["processed"]) + len(summary["blocked"]) >= 1
