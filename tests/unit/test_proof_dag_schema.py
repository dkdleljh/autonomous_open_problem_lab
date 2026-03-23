from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.apps.proof_engine import ProofEngine
from aopl.core.types import PipelineStage, ProblemRecord


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def assert_proof_dag_schema(payload: dict[str, object]) -> None:
    for key in ["problem_id", "root_node", "target_node", "nodes", "edges"]:
        assert key in payload


def test_proof_dag_schema_validation(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_dag_schema",
        title="proof dag 스키마 테스트",
        domain="graph_theory",
        statement="그래프 구조의 DAG 생성을 점검한다.",
        assumptions=["그래프는 유한하다."],
        goal="정리 후보를 DAG로 표현한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)
    dag = ProofEngine(project_root).build(normalized)
    assert_proof_dag_schema(dag.to_dict())
