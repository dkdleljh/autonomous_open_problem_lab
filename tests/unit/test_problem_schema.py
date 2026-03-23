from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.harvester import Harvester
from aopl.apps.registry import Registry


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def assert_problem_schema(payload: dict[str, object]) -> None:
    for key in [
        "problem_id",
        "title",
        "domain",
        "statement",
        "assumptions",
        "goal",
        "aliases",
        "sources",
        "status",
    ]:
        assert key in payload


def test_problem_schema_validation(tmp_path):
    project_root = prepare_project_root(tmp_path)
    harvested = Harvester(project_root).harvest()
    records = Registry(project_root).register(harvested)
    assert_problem_schema(records[0].to_dict())
    assert "provenance" in records[0].metadata
