from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.harvester import Harvester
from aopl.apps.registry import Registry
from aopl.core.io_utils import read_json, write_json
from aopl.core.schema_utils import validate_schema
from aopl.core.types import PipelineStage


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_registry_register_is_idempotent_for_same_harvest(tmp_path):
    project_root = prepare_project_root(tmp_path)
    write_json(project_root / "data" / "registry" / "problem_registry.json", [])
    write_json(project_root / "data" / "registry" / "status_history.json", [])
    harvested = Harvester(project_root).harvest()
    registry = Registry(project_root)

    first_records = registry.register(harvested)
    second_records = registry.register(harvested)

    history = read_json(project_root / "data" / "registry" / "status_history.json", default=[])
    bootstrap_events = [item for item in history if item.get("reason") == "registry bootstrap"]

    assert len(first_records) == len(second_records)
    assert len(bootstrap_events) == len(first_records)


def test_registry_preserves_existing_status_when_re_registering(tmp_path):
    project_root = prepare_project_root(tmp_path)
    write_json(project_root / "data" / "registry" / "problem_registry.json", [])
    write_json(project_root / "data" / "registry" / "status_history.json", [])
    harvested = Harvester(project_root).harvest()
    registry = Registry(project_root)

    records = registry.register(harvested)
    registry.update_status(records[0].problem_id, PipelineStage.BLOCKED, "test block")
    refreshed = registry.register(harvested)

    assert refreshed[0].status == PipelineStage.BLOCKED


def test_registry_persists_harvest_provenance_metadata(tmp_path):
    project_root = prepare_project_root(tmp_path)
    harvested = Harvester(project_root).harvest()
    records = Registry(project_root).register(harvested)

    provenance = records[0].metadata.get("provenance", {})

    assert provenance.get("harvest_batch_id", "").startswith("harvest_")
    assert provenance.get("source_signature")
    assert provenance.get("candidate_hash")
    assert isinstance(provenance.get("source_hashes"), list)


def test_registry_and_history_files_are_schema_valid(tmp_path):
    project_root = prepare_project_root(tmp_path)
    harvested = Harvester(project_root).harvest()
    registry = Registry(project_root)
    records = registry.register(harvested)
    registry.update_status(records[0].problem_id, PipelineStage.BLOCKED, "schema validation")

    registry_payload = read_json(project_root / "data" / "registry" / "problem_registry.json", default=[])
    history_payload = read_json(project_root / "data" / "registry" / "status_history.json", default=[])

    validate_schema(project_root, "problem_registry_schema", registry_payload)
    validate_schema(project_root, "status_history_schema", history_payload)
