from __future__ import annotations

import json
import shutil
from pathlib import Path

from aopl.apps.orchestrator import Orchestrator
from aopl.core.gates import GatePolicy
from aopl.core.io_utils import read_yaml, write_yaml
from aopl.core.types import PipelineStage, ProblemRecord, ProofDAG, ProofNode


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_proof_integrity_blocks_missing_dependency_edge(tmp_path):
    project_root = prepare_project_root(tmp_path)
    dag = ProofDAG(
        problem_id="prob_bad_dag",
        backend="real",
        root_node="n0",
        target_node="n2",
        nodes=[
            ProofNode("n0", "definition", "정의", "기본 정의", [], "ready"),
            ProofNode("n1", "lemma", "보조정리", "중간 정리", ["n0"], "candidate"),
            ProofNode("n2", "theorem", "주정리", "목표", ["n1"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n2"}],
    )

    passed, reason = GatePolicy(project_root).proof_integrity(dag.to_dict())

    assert passed is False
    assert "일치하지 않음" in reason


def test_orchestrator_blocks_runtime_exception_per_record(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["transient_failure_escalation_threshold"] = 10
    runtime["transient_failure_stage_thresholds"] = {"Normalize": 10}
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    queue_config = read_yaml(queue_file, default={})
    queue_config.setdefault("retry_policy", {})
    queue_config["retry_policy"]["backoff_seconds"] = 0
    write_yaml(queue_file, queue_config)

    target_problem_id = "prob_runtime_failure"

    original_normalize = Orchestrator.__init__

    def patched_init(self, root):
        original_normalize(self, root)
        original_method = self.normalizer.normalize

        def failing_normalize(record):
            if record.problem_id == target_problem_id:
                raise RuntimeError("injected normalize failure")
            return original_method(record)

        self.normalizer.normalize = failing_normalize

    monkeypatch.setattr("aopl.apps.orchestrator.Orchestrator.__init__", patched_init)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "Runtime Failure",
    "domain": "graph_theory",
    "statement": "그래프 이론 파이프라인에서 런타임 실패를 유도하는 충분히 긴 설명문이다.",
    "assumptions": ["그래프는 유한하다."],
    "goal": "정규화 단계에서 의도적으로 런타임 예외를 주입해 격리 동작을 검증한다.",
    "aliases": [],
    "sources": [
      {"name": "src1", "url": "https://example.org/1", "type": "registry", "reliability": 0.95}
    ]
  },
  {
    "title": "Healthy Problem",
    "domain": "number_theory",
    "statement": "정수론 파이프라인에서 정상 경로를 검증하기 위한 충분히 긴 설명문이다.",
    "assumptions": ["정수 집합에서 합동 연산을 사용한다."],
    "goal": "반례 완화형과 proof chain을 통해 정상적으로 릴리즈 경로까지 진행한다.",
    "aliases": [],
    "sources": [
      {"name": "src2", "url": "https://example.org/2", "type": "registry", "reliability": 0.95}
    ],
    "metadata": {
      "counterexample_search_spec": {
        "type": "integer_forbidden_residue",
        "modulus": 2,
        "forbidden_residue": 0,
        "start": 1,
        "weak_variant_recommendation": "n을 홀수로 제한한다."
      },
      "proof_search_spec": {
        "root_title": "기초 정의 고정",
        "lemma_chain": [{"title": "약화형 보조정리", "statement": "n을 홀수로 제한한다."}],
        "theorem_title": "주정리",
        "theorem_statement": "정상 목표"
      }
    }
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run()

    blocked_ids = {item["problem_id"] for item in summary["blocked"]}
    processed_ids = {item["problem_id"] for item in summary["processed"]}

    assert target_problem_id in blocked_ids
    assert "prob_healthy_problem" in processed_ids
    assert any("런타임 예외" in item["reason"] for item in summary["blocked"])
    blocked_item = next(item for item in summary["blocked"] if item["problem_id"] == target_problem_id)
    assert blocked_item["failure_class"] == "transient"
    assert blocked_item["stage"] == "HARVESTED"


def test_orchestrator_retries_transient_stage_failure_and_writes_incident_summary(
    tmp_path, monkeypatch
):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["max_retry_per_stage"] = 1
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    queue_config = read_yaml(queue_file, default={})
    queue_config.setdefault("retry_policy", {})
    queue_config["retry_policy"]["backoff_seconds"] = 0
    write_yaml(queue_file, queue_config)

    original_normalize = __import__("aopl.apps.normalizer", fromlist=["Normalizer"]).Normalizer.normalize
    attempts = {"count": 0}

    def flaky_normalize(self, record):
        if record.problem_id == "prob_retry_candidate" and attempts["count"] == 0:
            attempts["count"] += 1
            raise RuntimeError("transient normalize failure")
        return original_normalize(self, record)

    monkeypatch.setattr("aopl.apps.normalizer.Normalizer.normalize", flaky_normalize)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "Retry Candidate",
    "domain": "number_theory",
    "statement": "정수론 파이프라인 재시도 성공을 확인하기 위한 충분히 긴 설명문이다.",
    "assumptions": ["정수 집합에서 합동 연산을 사용한다."],
    "goal": "초기 예외 이후 재시도로 정상 처리됨을 검증한다.",
    "aliases": [],
    "sources": [
      {"name": "src", "url": "https://example.org/retry", "type": "registry", "reliability": 0.95}
    ],
    "metadata": {
      "counterexample_search_spec": {
        "type": "integer_forbidden_residue",
        "modulus": 2,
        "forbidden_residue": 0,
        "start": 1,
        "weak_variant_recommendation": "n을 홀수로 제한한다."
      },
      "proof_search_spec": {
        "root_title": "기초 정의 고정",
        "lemma_chain": [{"title": "약화형 보조정리", "statement": "n을 홀수로 제한한다."}],
        "theorem_title": "주정리",
        "theorem_statement": "정상 목표"
      }
    }
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run()

    assert summary["processed"]
    assert not summary["blocked"]
    audit_lines = (
        project_root / "data" / "audit_logs" / "pipeline_audit.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line) for line in audit_lines]
    assert any(item["gate_name"] == "Normalize Retry" for item in events)

    incident_summary = json.loads(
        (project_root / "data" / "audit_logs" / "last_incident_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert incident_summary["processed_count"] == 1
    assert incident_summary["blocked_count"] == 0
    assert incident_summary["failure_class_summary"] == {}
    assert incident_summary["policy_context"]["transient_failure_lookback_days"] >= 1


def test_orchestrator_does_not_retry_permanent_failure(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["max_retry_per_stage"] = 3
    write_yaml(runtime_file, runtime)
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    queue_config = read_yaml(queue_file, default={})
    queue_config.setdefault("retry_policy", {})
    queue_config["retry_policy"]["backoff_seconds"] = 0
    write_yaml(queue_file, queue_config)

    calls = {"count": 0}
    original_normalize = __import__("aopl.apps.normalizer", fromlist=["Normalizer"]).Normalizer.normalize

    def permanent_failure(self, record):
        if record.problem_id == "prob_runtime_failure":
            calls["count"] += 1
            raise ValueError("permanent normalize failure")
        return original_normalize(self, record)

    monkeypatch.setattr("aopl.apps.normalizer.Normalizer.normalize", permanent_failure)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "Runtime Failure",
    "domain": "graph_theory",
    "statement": "그래프 이론 파이프라인에서 영구 실패를 유도하는 충분히 긴 설명문이다.",
    "assumptions": ["그래프는 유한하다."],
    "goal": "ValueError는 재시도 없이 즉시 차단되어야 한다.",
    "aliases": [],
    "sources": [
      {"name": "src1", "url": "https://example.org/1", "type": "registry", "reliability": 0.95}
    ]
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run()

    assert calls["count"] == 1
    assert summary["blocked"]
    assert summary["blocked"][0]["failure_class"] == "permanent"
    audit_lines = (
        project_root / "data" / "audit_logs" / "pipeline_audit.jsonl"
    ).read_text(encoding="utf-8").strip().splitlines()
    retry_events = [json.loads(line) for line in audit_lines if "Retry" in line]
    assert len(retry_events) == 1


def test_orchestrator_escalates_repeated_transient_failure_to_permanent(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["max_retry_per_stage"] = 3
    runtime["transient_failure_escalation_threshold"] = 2
    runtime["transient_failure_stage_thresholds"] = {"Normalize": 2}
    write_yaml(runtime_file, runtime)
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    queue_config = read_yaml(queue_file, default={})
    queue_config.setdefault("retry_policy", {})
    queue_config["retry_policy"]["backoff_seconds"] = 0
    write_yaml(queue_file, queue_config)

    audit_file = project_root / "data" / "audit_logs" / "pipeline_audit.jsonl"
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.write_text(
        json.dumps(
            {
                "problem_id": "prob_runtime_failure",
                "stage": "HARVESTED",
                "gate_name": "Normalize Retry",
                "passed": False,
                "reason": "Normalize 실행 예외: previous transient failure",
                "timestamp": "2026-03-24T00:00:00+00:00",
                "metadata": {"failure_class": "transient"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    calls = {"count": 0}
    original_normalize = __import__("aopl.apps.normalizer", fromlist=["Normalizer"]).Normalizer.normalize

    def transient_failure(self, record):
        if record.problem_id == "prob_runtime_failure":
            calls["count"] += 1
            raise RuntimeError("transient normalize failure")
        return original_normalize(self, record)

    monkeypatch.setattr("aopl.apps.normalizer.Normalizer.normalize", transient_failure)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "Runtime Failure",
    "domain": "graph_theory",
    "statement": "그래프 이론 파이프라인에서 반복 transient 실패를 유도하는 충분히 긴 설명문이다.",
    "assumptions": ["그래프는 유한하다."],
    "goal": "동일 단계 transient 실패가 누적되면 permanent 로 승격되어야 한다.",
    "aliases": [],
    "sources": [
      {"name": "src1", "url": "https://example.org/1", "type": "registry", "reliability": 0.95}
    ]
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run()

    assert calls["count"] == 1
    assert summary["blocked"][0]["failure_class"] == "permanent"
    audit_lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    retry_events = [
        json.loads(line)
        for line in audit_lines
        if json.loads(line).get("gate_name") == "Normalize Retry"
    ]
    assert retry_events
    assert retry_events[-1]["metadata"]["escalated_from_transient"] is True


def test_orchestrator_ignores_transient_history_outside_lookback_window(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["max_retry_per_stage"] = 0
    runtime["transient_failure_escalation_threshold"] = 2
    runtime["transient_failure_lookback_days"] = 1
    runtime["transient_failure_stage_thresholds"] = {"Normalize": 2}
    write_yaml(runtime_file, runtime)
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    queue_config = read_yaml(queue_file, default={})
    queue_config.setdefault("retry_policy", {})
    queue_config["retry_policy"]["backoff_seconds"] = 0
    write_yaml(queue_file, queue_config)

    audit_file = project_root / "data" / "audit_logs" / "pipeline_audit.jsonl"
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.write_text(
        json.dumps(
            {
                "problem_id": "prob_runtime_failure",
                "stage": "HARVESTED",
                "gate_name": "Normalize Retry",
                "passed": False,
                "reason": "old transient failure",
                "timestamp": "2026-03-01T00:00:00+00:00",
                "metadata": {"failure_class": "transient"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    original_normalize = __import__("aopl.apps.normalizer", fromlist=["Normalizer"]).Normalizer.normalize

    def transient_failure(self, record):
        if record.problem_id == "prob_runtime_failure":
            raise RuntimeError("transient normalize failure")
        return original_normalize(self, record)

    monkeypatch.setattr("aopl.apps.normalizer.Normalizer.normalize", transient_failure)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "Runtime Failure",
    "domain": "graph_theory",
    "statement": "오래된 transient 이력은 승격 집계에서 제외되는지 확인하는 충분히 긴 설명문이다.",
    "assumptions": ["그래프는 유한하다."],
    "goal": "lookback window 밖 retry 이력은 무시되어야 한다.",
    "aliases": [],
    "sources": [
      {"name": "src1", "url": "https://example.org/1", "type": "registry", "reliability": 0.95}
    ]
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run()

    assert summary["blocked"][0]["failure_class"] == "transient"


def test_orchestrator_uses_stage_specific_escalation_threshold(tmp_path, monkeypatch):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["max_retry_per_stage"] = 1
    runtime["transient_failure_escalation_threshold"] = 5
    runtime["transient_failure_stage_thresholds"] = {"Normalize": 2}
    write_yaml(runtime_file, runtime)
    queue_file = project_root / "configs" / "global" / "queue.yaml"
    queue_config = read_yaml(queue_file, default={})
    queue_config.setdefault("retry_policy", {})
    queue_config["retry_policy"]["backoff_seconds"] = 0
    write_yaml(queue_file, queue_config)

    audit_file = project_root / "data" / "audit_logs" / "pipeline_audit.jsonl"
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.write_text(
        json.dumps(
            {
                "problem_id": "prob_runtime_failure",
                "stage": "HARVESTED",
                "gate_name": "Normalize Retry",
                "passed": False,
                "reason": "recent transient failure",
                "timestamp": "2026-03-24T00:00:00+00:00",
                "metadata": {"failure_class": "transient"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    original_normalize = __import__("aopl.apps.normalizer", fromlist=["Normalizer"]).Normalizer.normalize

    def transient_failure(self, record):
        if record.problem_id == "prob_runtime_failure":
            raise RuntimeError("transient normalize failure")
        return original_normalize(self, record)

    monkeypatch.setattr("aopl.apps.normalizer.Normalizer.normalize", transient_failure)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "Runtime Failure",
    "domain": "graph_theory",
    "statement": "단계별 승격 임계값이 전역값보다 우선하는지 확인하는 충분히 긴 설명문이다.",
    "assumptions": ["그래프는 유한하다."],
    "goal": "Normalize 단계는 별도 threshold 2 로 permanent 승격되어야 한다.",
    "aliases": [],
    "sources": [
      {"name": "src1", "url": "https://example.org/1", "type": "registry", "reliability": 0.95}
    ]
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run()

    assert summary["blocked"][0]["failure_class"] == "permanent"
