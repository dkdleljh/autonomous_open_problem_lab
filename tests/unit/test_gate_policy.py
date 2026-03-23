from __future__ import annotations

import shutil
from pathlib import Path

from aopl.core.gates import GatePolicy
from aopl.core.io_utils import read_yaml, write_yaml


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_gate_policy_release_blocks_demo_by_default(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime = read_yaml(project_root / "configs" / "global" / "runtime.yaml", default={})
    gates = GatePolicy(project_root, runtime)
    package_dir = project_root / "data" / "paper_assets" / "releases"
    package_dir.mkdir(parents=True, exist_ok=True)
    submission = {
        "package_file": "data/paper_assets/releases/a.zip",
        "source_bundle_file": "data/paper_assets/releases/a.tar.gz",
        "checksum_file": "data/paper_assets/releases/a.txt",
        "release_notes_file": "data/paper_assets/releases/a.md",
    }
    for rel in submission.values():
        (project_root / rel).write_text("x", encoding="utf-8")

    passed, reason = gates.release(
        submission,
        {"backend": "demo", "pdf_build_success": True, "pdf_artifact_kind": "latex_build"},
        {"demo_mode": True},
        {"passed": True},
        {"backend": "demo", "build_success": True, "obligations_unresolved": []},
    )

    assert passed is False
    assert "demo 문제" in reason


def test_gate_policy_release_can_be_relaxed(tmp_path):
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
    gates = GatePolicy(project_root, runtime)
    submission = {
        "package_file": "data/paper_assets/releases/a.zip",
        "source_bundle_file": "data/paper_assets/releases/a.tar.gz",
        "checksum_file": "data/paper_assets/releases/a.txt",
        "release_notes_file": "data/paper_assets/releases/a.md",
    }
    for rel in submission.values():
        (project_root / rel).parent.mkdir(parents=True, exist_ok=True)
        (project_root / rel).write_text("x", encoding="utf-8")

    passed, reason = gates.release(
        submission,
        {"backend": "demo", "pdf_build_success": False, "pdf_artifact_kind": "manual_bundle"},
        {"demo_mode": True},
        {"passed": True},
        {"backend": "demo", "build_success": False, "obligations_unresolved": []},
    )

    assert passed is True
    assert reason == "Release Gate 통과"
