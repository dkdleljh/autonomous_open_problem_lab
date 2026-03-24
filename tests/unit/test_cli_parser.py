from __future__ import annotations

import json
import shutil
from argparse import Namespace
from pathlib import Path

import pytest

import aopl.cli.main as cli_main
from aopl.apps.orchestrator import Orchestrator
from aopl.cli.main import (
    _command_doctor,
    _command_submission,
    _command_verify,
    _load_normalized,
    build_parser,
)
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
    doctor_report_file = project_root / "data" / "audit_logs" / "last_doctor_report.json"

    assert "doctor_score" in payload
    assert "checks" in payload
    assert "summary" in payload
    assert any(item["name"] == "핵심 한글 문서" for item in payload["checks"])
    assert "active_profile_score" in payload
    assert "strict_passed" in payload
    assert "incident_summary" in payload
    assert "runtime_policy_summary" in payload
    assert "policy_lint_summary" in payload
    assert any(item["name"] == "릴리즈 안전 정책" for item in payload["checks"])
    assert doctor_report_file.exists()
    stored_payload = json.loads(doctor_report_file.read_text(encoding="utf-8"))
    assert stored_payload["doctor_score"] == payload["doctor_score"]


def test_cli_doctor_includes_last_incident_summary_when_present(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)
    incident_path = project_root / "data" / "audit_logs" / "last_incident_summary.json"
    incident_path.parent.mkdir(parents=True, exist_ok=True)
    incident_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-03-24T00:00:00+00:00",
                "total_records": 1,
                "processed_count": 0,
                "blocked_count": 1,
                "runtime_exception_count": 1,
                "failure_class_summary": {"transient": 1},
                "policy_context": {
                    "transient_failure_lookback_days": 7,
                    "default_transient_failure_escalation_threshold": 3,
                    "stage_transient_failure_thresholds": {"Normalize": 3},
                },
                "top_block_reasons": [{"reason": "sample", "count": 1}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    _command_doctor(Namespace(root=str(project_root), profile=None, strict=False, min_score=None))
    payload = json.loads(capsys.readouterr().out)

    assert payload["incident_summary"]["blocked_count"] == 1
    assert payload["incident_summary"]["failure_class_summary"]["transient"] == 1
    assert payload["incident_summary"]["policy_context"]["transient_failure_lookback_days"] == 7


def test_cli_doctor_strict_exits_when_policy_unmet(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)

    with pytest.raises(SystemExit, match="1"):
        _command_doctor(
            Namespace(root=str(project_root), profile="local", strict=True, min_score=None)
        )

    payload = json.loads(capsys.readouterr().out)
    assert payload["active_profile"] == "local"
    assert payload["strict_passed"] is False
    assert payload["blocking_checks"]


def test_cli_doctor_flags_risky_policy_configuration(tmp_path, capsys):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    runtime = read_yaml(runtime_file, default={})
    queue = read_yaml(queue_file, default={})
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": False,
    }
    runtime["max_retry_per_stage"] = 0
    runtime["transient_failure_lookback_days"] = 1
    runtime["transient_failure_escalation_threshold"] = 1
    runtime["transient_failure_stage_thresholds"] = {"Proof": 2, "Formalization": 2}
    queue["scheduling"] = {"unattended": True}
    queue["retry_policy"] = {"max_attempts": 1, "backoff_seconds": 0}
    write_yaml(runtime_file, runtime)
    write_yaml(queue_file, queue)

    _command_doctor(Namespace(root=str(project_root), profile=None, strict=False, min_score=None))
    payload = json.loads(capsys.readouterr().out)

    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["무인 재시도 정책"]["passed"] is False
    assert checks["릴리즈 안전 정책"]["passed"] is False
    assert checks["Transient 승격 정책"]["passed"] is False
    assert payload["policy_lint_summary"]["failed_policy_checks"] >= 3


def test_cli_doctor_accepts_github_fallback_sources(tmp_path, capsys, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    original = cli_main._run_optional

    def fake_run_optional(command: list[str], cwd: Path) -> tuple[int, str, str]:
        if command == ["gh", "auth", "token"]:
            return 0, "gho_test_token", ""
        if command == ["git", "remote", "get-url", "origin"]:
            return 0, "https://github.com/example/autonomous_open_problem_lab.git", ""
        return original(command, cwd)

    monkeypatch.setattr(cli_main, "_run_optional", fake_run_optional)
    _command_doctor(
        Namespace(root=str(project_root), profile="github_release", strict=False, min_score=None)
    )
    payload = json.loads(capsys.readouterr().out)

    checks = {item["name"]: item for item in payload["checks"]}
    assert checks["GITHUB_TOKEN"]["passed"] is True
    assert checks["GITHUB_REPOSITORY"]["passed"] is True
