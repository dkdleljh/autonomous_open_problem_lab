from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.core.io_utils import read_yaml, write_yaml
from aopl.core.types import PipelineStage, ProblemRecord
from aopl.services.engine_factory import EngineFactory


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_real_counterexample_backend_runs_structured_integer_search(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["counterexample_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_counterexample",
        title="실백엔드 반례 테스트",
        domain="number_theory",
        statement="모든 양의 정수 n에 대해 어떤 조건이 성립한다고 가정한다.",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="강한형 명제가 모든 n에 대해 유지된다고 주장한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={
            "counterexample_search_spec": {
                "type": "integer_forbidden_residue",
                "modulus": 2,
                "forbidden_residue": 0,
                "start": 1,
                "reason": "짝수 n에서 강한형이 실패한다.",
                "weak_variant_recommendation": "n을 홀수로 제한한다.",
            }
        },
    )

    normalized = Normalizer(project_root).normalize(record)
    engine = EngineFactory(project_root).counterexample_engine()
    report = engine.run(normalized, bound=20)

    assert report.backend == "real"
    assert report.found_counterexample is True
    assert report.counterexample is not None
    assert report.counterexample["n"] == 2
    assert report.weak_variant_recommendation == "n을 홀수로 제한한다."


def test_real_counterexample_backend_returns_no_counterexample_without_spec(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["counterexample_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_counterexample_none",
        title="실백엔드 미탐지 테스트",
        domain="number_theory",
        statement="구조화된 탐색 명세가 없는 문제",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="탐색 명세가 없으면 즉시 반례를 단정하지 않는다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={},
    )

    normalized = Normalizer(project_root).normalize(record)
    engine = EngineFactory(project_root).counterexample_engine()
    report = engine.run(normalized, bound=20)

    assert report.backend == "real"
    assert report.found_counterexample is False
    assert report.counterexample is None


def test_real_counterexample_backend_supports_forbidden_values_spec(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["counterexample_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_counterexample_values",
        title="실백엔드 값 집합 반례 테스트",
        domain="number_theory",
        statement="특정 정수 집합에서 반례를 찾는다.",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="금지된 값 집합 중 첫 반례를 찾는다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={
            "counterexample_search_spec": {
                "type": "integer_forbidden_values",
                "values": [11, 4, 9],
                "start": 3,
                "reason": "작은 금지 값에서 실패한다.",
                "weak_variant_recommendation": "금지 값을 제외한다.",
            }
        },
    )

    normalized = Normalizer(project_root).normalize(record)
    engine = EngineFactory(project_root).counterexample_engine()
    report = engine.run(normalized, bound=20)

    assert report.backend == "real"
    assert report.found_counterexample is True
    assert report.counterexample is not None
    assert report.counterexample["n"] == 4
    assert report.weak_variant_recommendation == "금지 값을 제외한다."


def test_real_counterexample_backend_supports_interval_spec(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["counterexample_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_counterexample_interval",
        title="실백엔드 구간 반례 테스트",
        domain="number_theory",
        statement="특정 구간에서 반례를 찾는다.",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="금지 구간의 첫 값을 찾는다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={
            "counterexample_search_spec": {
                "type": "integer_range_membership",
                "interval_start": 6,
                "interval_end": 9,
                "start": 1,
                "reason": "금지 구간 내부에서 실패한다.",
                "weak_variant_recommendation": "구간 밖으로 제한한다.",
            }
        },
    )

    normalized = Normalizer(project_root).normalize(record)
    engine = EngineFactory(project_root).counterexample_engine()
    report = engine.run(normalized, bound=20)

    assert report.backend == "real"
    assert report.found_counterexample is True
    assert report.counterexample is not None
    assert report.counterexample["n"] == 6
    assert report.counterexample["interval"] == [6, 9]
