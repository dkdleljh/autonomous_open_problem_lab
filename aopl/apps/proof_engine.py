from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from aopl.core.io_utils import ensure_dir, write_json
from aopl.core.types import NormalizedProblem, ProofDAG, ProofNode


def _is_dag(nodes: list[str], edges: list[tuple[str, str]]) -> bool:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        adjacency[src].append(dst)
    color: dict[str, int] = dict.fromkeys(nodes, 0)

    def dfs(node: str) -> bool:
        color[node] = 1
        for nxt in adjacency.get(node, []):
            if color.get(nxt, 0) == 1:
                return False
            if color.get(nxt, 0) == 0 and not dfs(nxt):
                return False
        color[node] = 2
        return True

    for node in nodes:
        if color.get(node, 0) == 0 and not dfs(node):
            return False
    return True


class ProofEngine:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.dag_dir = ensure_dir(root / "data" / "proof_dag")
        self.memory_file = self.dag_dir / "failure_memory.json"

    def build(self, problem: NormalizedProblem) -> ProofDAG:
        nodes = [
            ProofNode(
                node_id="n0",
                node_type="definition",
                title="정의 정렬",
                statement="정의와 표기법을 고정하여 이후 단계의 해석 충돌을 제거한다.",
                dependencies=[],
                status="ready",
            ),
            ProofNode(
                node_id="n1",
                node_type="lemma",
                title="보조정리 후보 생성",
                statement="약화형 명제에서 필요한 불변량 후보를 생성한다.",
                dependencies=["n0"],
                status="candidate",
            ),
            ProofNode(
                node_id="n2",
                node_type="lemma",
                title="환원 경로 구축",
                statement="주명제를 보조정리들로 환원하는 경로를 명시한다.",
                dependencies=["n1"],
                status="candidate",
            ),
            ProofNode(
                node_id="n3",
                node_type="theorem",
                title="주정리 초안",
                statement=problem.target,
                dependencies=["n2"],
                status="draft",
            ),
        ]

        edges = []
        for node in nodes:
            for dep in node.dependencies:
                edges.append({"from": dep, "to": node.node_id})

        if not _is_dag(
            [node.node_id for node in nodes], [(edge["from"], edge["to"]) for edge in edges]
        ):
            raise ValueError("proof DAG 생성 실패: 순환이 감지되었습니다.")

        dag = ProofDAG(
            problem_id=problem.problem_id,
            root_node="n0",
            target_node="n3",
            nodes=nodes,
            edges=edges,
        )

        write_json(self.dag_dir / f"{problem.problem_id}_proof_dag.json", dag.to_dict())
        write_json(self.memory_file, {"last_problem_id": problem.problem_id, "last_failures": []})
        return dag
