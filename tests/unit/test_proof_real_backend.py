from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.core.io_utils import read_yaml, write_yaml
from aopl.core.types import CounterexampleReport, PipelineStage, ProblemRecord
from aopl.services.engine_factory import EngineFactory


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_real_proof_backend_builds_from_structured_spec(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["proof_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_proof_spec",
        title="실백엔드 proof spec 테스트",
        domain="number_theory",
        statement="정수론 proof spec 테스트",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="강한형 명제를 약화형과 보조정리 체인으로 환원한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={
            "proof_search_spec": {
                "root_title": "기초 정의 고정",
                "lemma_chain": [
                    {
                        "title": "짝수 잔여류 분리",
                        "statement": "짝수 잔여류를 별도 경우로 분리한다.",
                    },
                    {
                        "title": "홀수 약화형 환원",
                        "statement": "홀수 영역의 약화형으로 환원한다.",
                    },
                ],
                "theorem_title": "주정리 초안",
                "theorem_statement": "홀수 영역에서 목표 명제가 유지됨을 보인다.",
            }
        },
    )

    normalized = Normalizer(project_root).normalize(record)
    engine = EngineFactory(project_root).proof_engine()
    dag = engine.build(normalized)

    assert dag.backend == "real"
    assert dag.root_node == "n0"
    assert dag.target_node == "n3"
    assert [node.title for node in dag.nodes[1:3]] == ["짝수 잔여류 분리", "홀수 약화형 환원"]


def test_real_proof_backend_derives_dag_without_explicit_spec(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["proof_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_proof_default",
        title="실백엔드 proof 기본 테스트",
        domain="graph_theory",
        statement="그래프 구조의 기본 proof DAG 생성",
        assumptions=["그래프는 유한하다."],
        goal="정리 후보를 DAG로 표현한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={},
    )

    normalized = Normalizer(project_root).normalize(record)
    engine = EngineFactory(project_root).proof_engine()
    dag = engine.build(normalized)

    assert dag.backend == "real"
    assert len(dag.nodes) == 4
    assert dag.nodes[1].title == "도메인 분해 보조정리"
    assert dag.nodes[-1].statement == normalized.target


def test_real_proof_backend_uses_counterexample_guidance_in_derived_dag(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["proof_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_proof_guided",
        title="실백엔드 proof 반례 연동 테스트",
        domain="number_theory",
        statement="정수론 구조의 기본 proof DAG 생성",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="정리 후보를 DAG로 표현한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={},
    )

    normalized = Normalizer(project_root).normalize(record)
    report = CounterexampleReport(
        problem_id=record.problem_id,
        backend="real",
        checked_variant="strong_variant",
        found_counterexample=True,
        counterexample={"n": 4},
        explored_bound=24,
        seed=20260324,
        elapsed_seconds=0.05,
        weak_variant_recommendation="n을 홀수로 제한한다.",
    )
    engine = EngineFactory(project_root).proof_engine()
    dag = engine.build(normalized, report)

    assert dag.backend == "real"
    assert "반례 탐색 상한 24" in dag.nodes[1].statement
    assert "n을 홀수로 제한한다." in dag.nodes[2].statement
    assert dag.nodes[2].title == "약화형 환원 경로"
