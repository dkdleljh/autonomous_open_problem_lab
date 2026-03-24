from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from aopl.core.config_store import ConfigStore
from aopl.core.io_utils import read_yaml, write_yaml


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_config_store_loads_runtime_and_domain_config(tmp_path):
    project_root = prepare_project_root(tmp_path)
    store = ConfigStore(project_root)

    runtime = store.runtime()
    domain = store.problem_domain("graph_theory")

    assert runtime["engines"]["proof_backend"] == "demo"
    assert domain["priority_boost"] == 1.05


def test_config_store_rejects_invalid_runtime_backend(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["proof_backend"] = "bad"
    write_yaml(runtime_file, runtime)

    with pytest.raises(ValueError, match="proof_backend"):
        ConfigStore(project_root).runtime()


def test_config_store_rejects_invalid_transient_failure_escalation_threshold(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["transient_failure_escalation_threshold"] = 0
    write_yaml(runtime_file, runtime)

    with pytest.raises(ValueError, match="transient_failure_escalation_threshold"):
        ConfigStore(project_root).runtime()


def test_config_store_rejects_invalid_transient_failure_stage_thresholds(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["transient_failure_stage_thresholds"] = {"Normalize": 0}
    write_yaml(runtime_file, runtime)

    with pytest.raises(ValueError, match="transient_failure_stage_thresholds"):
        ConfigStore(project_root).runtime()


def test_config_store_rejects_invalid_scoring_threshold(tmp_path):
    project_root = prepare_project_root(tmp_path)
    scoring_file = project_root / "configs" / "scoring" / "default.yaml"
    scoring = read_yaml(scoring_file, default={})
    scoring.setdefault("selection", {})
    scoring["selection"]["min_score"] = 1.5
    write_yaml(scoring_file, scoring)

    with pytest.raises(ValueError, match="min_score"):
        ConfigStore(project_root).scoring()


def test_config_store_loads_quality_policy(tmp_path):
    project_root = prepare_project_root(tmp_path)

    policy = ConfigStore(project_root).quality_policy()

    assert policy["doctor"]["default_profile"] == "local"
    assert "github_release" in policy["doctor"]["profiles"]


def test_config_store_rejects_invalid_quality_policy_threshold(tmp_path):
    project_root = prepare_project_root(tmp_path)
    policy_file = project_root / "configs" / "global" / "quality_policy.yaml"
    policy = read_yaml(policy_file, default={})
    policy.setdefault("doctor", {}).setdefault("profiles", {}).setdefault("local", {})
    policy["doctor"]["profiles"]["local"]["min_score"] = 101
    write_yaml(policy_file, policy)

    with pytest.raises(ValueError, match="min_score"):
        ConfigStore(project_root).quality_policy()
