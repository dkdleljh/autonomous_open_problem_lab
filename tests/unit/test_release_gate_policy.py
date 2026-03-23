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


def test_release_gate_blocks_demo_release_by_default(tmp_path):
    project_root = prepare_project_root(tmp_path)
    summary = Orchestrator(project_root).run(limit=1)

    assert not summary["processed"]
    assert summary["blocked"]
    assert (
        "demo 문제" in summary["blocked"][0]["reason"]
        or "형식화 빌드 성공 필요" in summary["blocked"][0]["reason"]
        or "논문 PDF 빌드 성공 필요" in summary["blocked"][0]["reason"]
    )


def test_release_gate_can_be_relaxed_for_local_demo_runs(tmp_path):
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
    assert not summary["blocked"]
