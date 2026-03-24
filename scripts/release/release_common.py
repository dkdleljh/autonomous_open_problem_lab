from __future__ import annotations

import json
from pathlib import Path


def read_json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def doctor_report_path(repo: Path) -> Path:
    return repo / "data" / "audit_logs" / "last_doctor_report.json"


def incident_summary_path(repo: Path) -> Path:
    return repo / "data" / "audit_logs" / "last_incident_summary.json"


def doctor_report_hint(repo: Path) -> str:
    return f"확인 파일: {doctor_report_path(repo)}"


def incident_summary_hint(repo: Path) -> str:
    return f"확인 파일: {incident_summary_path(repo)}"


def load_doctor_report(repo: Path) -> dict[str, object]:
    return read_json_file(doctor_report_path(repo))


def load_incident_summary(repo: Path) -> dict[str, object]:
    return read_json_file(incident_summary_path(repo))


def summarize_doctor_failure(stdout: str) -> str:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    failed_checks = payload.get("blocking_checks", [])
    if not isinstance(failed_checks, list) or not failed_checks:
        return ""
    names = [
        item.get("name")
        for item in failed_checks
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    if not names:
        return ""
    return f"doctor strict 차단 항목: {', '.join(names)}"


def failed_policy_checks(doctor_summary: dict[str, object]) -> list[str]:
    return [
        item.get("name")
        for item in doctor_summary.get("checks", [])
        if isinstance(item, dict)
        and item.get("category") == "policy"
        and item.get("passed") is False
        and isinstance(item.get("name"), str)
    ]


def detect_operational_risks(repo: Path) -> list[str]:
    incident_summary = load_incident_summary(repo)
    doctor_summary = load_doctor_report(repo)
    risks: list[str] = []
    failure_class_summary = incident_summary.get("failure_class_summary", {})
    permanent_count = 0
    if isinstance(failure_class_summary, dict):
        permanent_count = int(failure_class_summary.get("permanent", 0))
    if permanent_count > 0:
        risks.append(f"permanent 실패가 최근 실행에서 {permanent_count}건 감지됨")
    policy_failures = failed_policy_checks(doctor_summary)
    if policy_failures:
        risks.append(f"doctor 정책 lint 실패 항목 존재: {policy_failures}")
    if doctor_summary.get("strict_passed", "unknown") is False:
        risks.append("doctor strict가 최근 실행에서 실패함")
    return risks
