from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


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


def test_generate_release_notes_includes_operational_state(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "generate_release_notes.py",
        "test_generate_release_notes_module",
    )
    audit_dir = project_root / "data" / "audit_logs"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "last_incident_summary.json").write_text(
        json.dumps(
            {
                "blocked_count": 2,
                "failure_class_summary": {"transient": 1, "permanent": 1},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_dir / "last_doctor_report.json").write_text(
        json.dumps(
            {
                "strict_passed": False,
                "policy_lint_summary": {"failed_policy_checks": 2},
                "checks": [
                    {
                        "name": "릴리즈 안전 정책",
                        "category": "policy",
                        "passed": False,
                    },
                    {
                        "name": "무인 재시도 정책",
                        "category": "policy",
                        "passed": False,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lines = module.build_operational_summary(project_root)

    rendered = "\n".join(lines)
    assert "## 운영 위험" in rendered
    assert "permanent 실패가 최근 실행에서 1건 감지됨" in rendered
    assert "doctor strict가 최근 실행에서 실패함" in rendered
    assert "최근 blocked 수: 2" in rendered
    assert "최근 failure class 요약: {'transient': 1, 'permanent': 1}" in rendered
    assert "doctor strict 통과: False" in rendered
    assert "doctor 정책 lint 실패 수: 2" in rendered
    assert "릴리즈 안전 정책" in rendered
    assert "무인 재시도 정책" in rendered


def test_generate_release_notes_marks_no_major_operational_risk(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "generate_release_notes.py",
        "test_generate_release_notes_module_safe",
    )
    audit_dir = project_root / "data" / "audit_logs"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "last_incident_summary.json").write_text(
        json.dumps(
            {
                "blocked_count": 0,
                "failure_class_summary": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_dir / "last_doctor_report.json").write_text(
        json.dumps(
            {
                "strict_passed": True,
                "policy_lint_summary": {"failed_policy_checks": 0},
                "checks": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rendered = "\n".join(module.build_operational_summary(project_root))

    assert "## 운영 위험" in rendered
    assert "중대 운영 위험 없음" in rendered


def test_detect_operational_risks_returns_messages(tmp_path):
    project_root = prepare_project_root(tmp_path)
    module = load_module(
        project_root / "scripts" / "release" / "generate_release_notes.py",
        "test_generate_release_notes_module_risks",
    )
    audit_dir = project_root / "data" / "audit_logs"
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "last_incident_summary.json").write_text(
        json.dumps(
            {"failure_class_summary": {"permanent": 1}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_dir / "last_doctor_report.json").write_text(
        json.dumps(
            {
                "strict_passed": False,
                "checks": [
                    {"name": "릴리즈 안전 정책", "category": "policy", "passed": False},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    risks = module.detect_operational_risks(project_root)

    assert any("permanent 실패" in item for item in risks)
    assert any("릴리즈 안전 정책" in item for item in risks)
    assert any("doctor strict" in item for item in risks)
