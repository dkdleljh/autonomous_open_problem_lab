from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal", "scripts"]:
        source = source_root / name
        if source.is_dir():
            shutil.copytree(source, root / name, dirs_exist_ok=True)
    return root


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_incident_summary(repo: Path, payload: dict[str, object]) -> None:
    path = repo / "data" / "audit_logs" / "last_incident_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_auto_update_allows_transient_incident_with_flag(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "auto_update.py",
        "test_auto_update_module",
    )
    write_incident_summary(
        project_root,
        {
            "blocked_count": 1,
            "failure_class_summary": {"transient": 1},
        },
    )

    module.enforce_incident_policy(project_root, block_on_permanent=False)


def test_auto_update_blocks_permanent_incident(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "auto_update.py",
        "test_auto_update_module_block",
    )
    write_incident_summary(
        project_root,
        {
            "blocked_count": 1,
            "failure_class_summary": {"permanent": 1},
        },
    )

    with pytest.raises(RuntimeError, match="permanent"):
        module.enforce_incident_policy(project_root, block_on_permanent=True)


def test_create_release_blocks_when_incident_summary_has_blocked_items(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "create_release.py",
        "test_create_release_module",
    )
    write_incident_summary(
        project_root,
        {
            "blocked_count": 1,
            "failure_class_summary": {"transient": 1},
        },
    )

    with pytest.raises(RuntimeError, match="blocked"):
        module.ensure_release_incident_policy(project_root, allow_transient_only=False)


def test_auto_update_reports_doctor_blocking_checks(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "auto_update.py",
        "test_auto_update_module_doctor",
    )
    stdout = json.dumps(
        {
            "blocking_checks": [
                {"name": "릴리즈 안전 정책", "detail": "sample"},
                {"name": "무인 재시도 정책", "detail": "sample"},
            ]
        },
        ensure_ascii=False,
    )

    with pytest.raises(RuntimeError, match="릴리즈 안전 정책"):
        module.require_success(
            1,
            ["python3", "-m", "aopl", "doctor", "--strict"],
            "",
            stdout,
            repo=project_root,
        )


def test_auto_update_reports_doctor_report_path(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "auto_update.py",
        "test_auto_update_module_doctor_path",
    )

    with pytest.raises(RuntimeError, match="last_doctor_report.json"):
        module.require_success(
            1,
            ["python3", "-m", "aopl", "doctor", "--strict"],
            "",
            json.dumps({"blocking_checks": [{"name": "릴리즈 안전 정책"}]}, ensure_ascii=False),
            repo=project_root,
        )


def test_create_release_reports_doctor_blocking_checks(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "create_release.py",
        "test_create_release_module_doctor",
    )
    stdout = json.dumps(
        {
            "blocking_checks": [
                {"name": "Transient 승격 정책", "detail": "sample"},
            ]
        },
        ensure_ascii=False,
    )
    completed = module.subprocess.CompletedProcess(
        args=["python3", "-m", "aopl", "doctor", "--strict"],
        returncode=1,
        stdout=stdout,
        stderr="",
    )
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: completed)

    with pytest.raises(RuntimeError, match="Transient 승격 정책"):
        module.run(["python3", "-m", "aopl", "doctor", "--strict"], project_root)


def test_create_release_generates_notes_with_risk_override_flag(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "create_release.py",
        "test_create_release_module_override",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> str:
        calls.append(command)
        return ""

    monkeypatch.setattr(module, "run", fake_run)
    notes_file = project_root / "data" / "paper_assets" / "releases" / "release_notes_v1.2.3.md"

    module.generate_release_notes(
        project_root,
        "python3",
        "v1.2.3",
        notes_file,
        allow_operational_risk=True,
    )

    assert calls
    assert calls[0][:2] == ["python3", "scripts/release/generate_release_notes.py"]
    assert "--fail-on-risk" in calls[0]
    assert "--allow-risk-override" in calls[0]


def test_create_release_generates_notes_without_risk_override_flag(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "create_release.py",
        "test_create_release_module_no_override",
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> str:
        calls.append(command)
        return ""

    monkeypatch.setattr(module, "run", fake_run)
    notes_file = project_root / "data" / "paper_assets" / "releases" / "release_notes_v1.2.3.md"

    module.generate_release_notes(
        project_root,
        "python3",
        "v1.2.3",
        notes_file,
        allow_operational_risk=False,
    )

    assert calls
    assert "--fail-on-risk" in calls[0]
    assert "--allow-risk-override" not in calls[0]


def test_auto_update_permanent_incident_error_includes_summary_path(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "auto_update.py",
        "test_auto_update_module_incident_path",
    )
    write_incident_summary(
        project_root,
        {
            "blocked_count": 1,
            "failure_class_summary": {"permanent": 1},
        },
    )

    with pytest.raises(RuntimeError, match="last_incident_summary.json"):
        module.enforce_incident_policy(project_root, block_on_permanent=True)
