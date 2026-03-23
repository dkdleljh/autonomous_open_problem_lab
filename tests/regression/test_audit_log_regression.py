from __future__ import annotations

import json
import shutil
from pathlib import Path

from aopl.apps.orchestrator import Orchestrator
from aopl.core.io_utils import read_yaml, write_yaml
from aopl.core.schema_utils import validate_schema


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_audit_log_contains_provenance_and_verification_metadata(tmp_path):
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

    audit_file = project_root / "data" / "audit_logs" / "pipeline_audit.jsonl"
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    events = [json.loads(line) for line in lines]
    problem_id = summary["processed"][0]["problem_id"]
    problem_events = [item for item in events if item.get("problem_id") == problem_id]
    for event in problem_events:
        validate_schema(project_root, "stage_event_schema", event)

    verification_event = next(
        item for item in reversed(problem_events) if item["gate_name"] == "Verification Gate"
    )
    release_event = next(
        item for item in reversed(problem_events) if item["gate_name"] == "Release Gate"
    )

    assert verification_event["metadata"]["harvest_batch_id"]
    assert "critical_issue_count" in verification_event["metadata"]
    assert "warning_count" in verification_event["metadata"]
    assert release_event["metadata"]["release_notes_file"]
    assert release_event["metadata"]["package_file"]
    assert "paper_pdf_artifact_kind" in release_event["metadata"]

    verification_log_file = project_root / "data" / "audit_logs" / "verification_log.jsonl"
    verification_lines = verification_log_file.read_text(encoding="utf-8").strip().splitlines()
    assert verification_lines
    verification_entries = [json.loads(line) for line in verification_lines]
    matching_entries = [
        item for item in verification_entries if item.get("problem_id") == problem_id
    ]
    assert matching_entries
    latest_verification_entry = matching_entries[-1]
    validate_schema(project_root, "verification_log_entry_schema", latest_verification_entry)
    assert "backend_summary" in latest_verification_entry
    assert "provenance_summary" in latest_verification_entry
