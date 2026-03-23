from __future__ import annotations

import json
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

from aopl.apps.orchestrator import Orchestrator
from aopl.cli.main import _command_doctor, _command_submission, _command_verify, _load_normalized, build_parser
from aopl.core.io_utils import read_json, read_yaml, write_json, write_yaml


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def reset_generated_artifacts(project_root: Path) -> None:
    targets = [
        project_root / "data" / "registry",
        project_root / "data" / "normalized",
        project_root / "data" / "proof_dag",
        project_root / "data" / "experiments",
        project_root / "data" / "theorem_store",
        project_root / "data" / "audit_logs",
        project_root / "papers" / "builds",
        project_root / "papers" / "ko",
        project_root / "papers" / "en",
        project_root / "papers" / "shared",
        project_root / "formal" / "generated_skeletons",
        project_root / "formal" / "proof_obligations",
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)


def test_cli_accepts_root_after_subcommand():
    parser = build_parser()
    args = parser.parse_args(["run-all", "--root", ".", "--limit", "1"])

    assert args.command == "run-all"
    assert args.root == "."
    assert args.limit == 1


def test_cli_accepts_doctor_subcommand():
    parser = build_parser()
    args = parser.parse_args(["doctor", "--root", ".", "--profile", "ci", "--strict"])

    assert args.command == "doctor"
    assert args.root == "."
    assert args.profile == "ci"
    assert args.strict is True


def test_cli_verify_prints_provenance_and_summary(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)
    reset_generated_artifacts(project_root)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)

    Orchestrator(project_root).run(limit=1)
    _command_verify(Namespace(root=str(project_root)))
    payload = json.loads(capsys.readouterr().out)

    assert payload["verified"] >= 1
    first = payload["reports"][0]
    assert "provenance_summary" in first
    assert "summary" in first
    assert "critical_issue_count" in first["summary"]
    assert "warning_count" in first["summary"]


def test_cli_submission_prints_submission_and_provenance(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)
    reset_generated_artifacts(project_root)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)

    Orchestrator(project_root).run(limit=1)
    _command_submission(Namespace(root=str(project_root)))
    payload = json.loads(capsys.readouterr().out)

    assert payload["submission_packages"]
    first = payload["submission_packages"][0]
    assert "provenance_summary" in first
    assert "submission" in first
    assert "verification_summary" in first["submission"]


def test_cli_loader_rejects_invalid_normalized_payload(tmp_path):
    project_root = prepare_project_root(tmp_path)
    reset_generated_artifacts(project_root)
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
    normalized_path = project_root / "data" / "normalized" / f"{problem_id}_normalized.json"
    payload = read_json(normalized_path, default={})
    payload.pop("target", None)
    write_json(normalized_path, payload)

    with pytest.raises(ValueError, match="normalized_problem_schema"):
        _load_normalized(project_root, problem_id)


def test_cli_doctor_prints_readiness_report(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)
    _command_doctor(Namespace(root=str(project_root), profile=None, strict=False, min_score=None))
    payload = json.loads(capsys.readouterr().out)

    assert "doctor_score" in payload
    assert "checks" in payload
    assert "summary" in payload
    assert any(item["name"] == "핵심 한글 문서" for item in payload["checks"])
    assert "active_profile_score" in payload
    assert "strict_passed" in payload


def test_cli_doctor_strict_exits_when_policy_unmet(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)

    with pytest.raises(SystemExit, match="1"):
        _command_doctor(Namespace(root=str(project_root), profile="local", strict=True, min_score=None))

    payload = json.loads(capsys.readouterr().out)
    assert payload["active_profile"] == "local"
    assert payload["strict_passed"] is False
    assert payload["blocking_checks"]
