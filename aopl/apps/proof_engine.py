from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from aopl.core.io_utils import ensure_dir, read_yaml, write_json
from aopl.core.schema_utils import validate_schema
from aopl.core.types import CounterexampleReport, NormalizedProblem, ProofDAG, ProofNode


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
    def __init__(self, root: Path, backend: str = "demo") -> None:
        self.root = root
        self.backend = backend
        self.dag_dir = ensure_dir(root / "data" / "proof_dag")
        self.memory_file = self.dag_dir / "failure_memory.json"

    def _write_dag(self, problem: NormalizedProblem, nodes: list[ProofNode]) -> ProofDAG:
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
            backend=self.backend,
            root_node=nodes[0].node_id,
            target_node=nodes[-1].node_id,
            nodes=nodes,
            edges=edges,
        )
        validate_schema(self.root, "proof_dag_schema", dag.to_dict())

        write_json(self.dag_dir / f"{problem.problem_id}_proof_dag.json", dag.to_dict())
        write_json(self.memory_file, {"last_problem_id": problem.problem_id, "last_failures": []})
        return dag

    def build(
        self,
        problem: NormalizedProblem,
        counterexample_report: CounterexampleReport | None = None,
    ) -> ProofDAG:
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
        return self._write_dag(problem, nodes)


class DemoProofEngine(ProofEngine):
    def __init__(self, root: Path) -> None:
        super().__init__(root, backend="demo")


class RealProofEngine(ProofEngine):
    def __init__(self, root: Path) -> None:
        super().__init__(root, backend="real")

    def _domain_config(self, problem: NormalizedProblem) -> dict:
        config_file = self.root / "configs" / "problems" / f"{problem.domain}.yaml"
        config = read_yaml(config_file, default={})
        return config if isinstance(config, dict) else {}

    def _spec_nodes(self, problem: NormalizedProblem, spec: dict) -> list[ProofNode]:
        root_title = spec.get("root_title", "정의와 가정 고정")
        root_statement = spec.get(
            "root_statement",
            f"객체 {', '.join(problem.objects)} 와 가정 {', '.join(problem.assumptions)} 를 고정한다.",
        )
        nodes = [
            ProofNode(
                node_id="n0",
                node_type="definition",
                title=str(root_title),
                statement=str(root_statement),
                dependencies=[],
                status="ready",
            )
        ]
        previous = "n0"
        lemma_chain = spec.get("lemma_chain", [])
        if isinstance(lemma_chain, list):
            for index, lemma in enumerate(lemma_chain, start=1):
                if not isinstance(lemma, dict):
                    continue
                node_id = f"n{index}"
                nodes.append(
                    ProofNode(
                        node_id=node_id,
                        node_type=str(lemma.get("node_type", "lemma")),
                        title=str(lemma.get("title", f"보조정리 {index}")),
                        statement=str(lemma.get("statement", problem.target)),
                        dependencies=[previous],
                        status=str(lemma.get("status", "candidate")),
                    )
                )
                previous = node_id
        theorem_id = f"n{len(nodes)}"
        nodes.append(
            ProofNode(
                node_id=theorem_id,
                node_type="theorem",
                title=str(spec.get("theorem_title", "주정리 초안")),
                statement=str(spec.get("theorem_statement", problem.target)),
                dependencies=[previous],
                status="draft",
            )
        )
        return nodes

    def _apply_counterexample_guidance(
        self,
        nodes: list[ProofNode],
        counterexample_report: CounterexampleReport | None = None,
    ) -> list[ProofNode]:
        weak_variant, explored_bound = self._counterexample_context(counterexample_report)
        if not nodes:
            return nodes
        if isinstance(weak_variant, str) and weak_variant.strip():
            target_index = 1 if len(nodes) > 1 else len(nodes) - 1
            node = nodes[target_index]
            if weak_variant not in node.statement:
                node.statement = f"{node.statement} 약화형 권고: {weak_variant}"
            if "약화형" not in node.title and node.node_type == "lemma":
                node.title = f"{node.title} 및 약화형 반영"
        if isinstance(explored_bound, int) and explored_bound > 0:
            root_node = nodes[0]
            bound_text = f"반례 탐색 상한 {explored_bound} 를 참고해 정의와 가정을 정렬한다."
            if str(explored_bound) not in root_node.statement:
                root_node.statement = f"{root_node.statement} {bound_text}"
        return nodes

    def _counterexample_context(
        self, counterexample_report: CounterexampleReport | None
    ) -> tuple[str | None, int | None]:
        if counterexample_report is None:
            return None, None
        weak_variant = counterexample_report.weak_variant_recommendation
        explored_bound = counterexample_report.explored_bound
        return weak_variant, explored_bound

    def _derived_nodes(
        self,
        problem: NormalizedProblem,
        counterexample_report: CounterexampleReport | None = None,
    ) -> list[ProofNode]:
        config = self._domain_config(problem)
        hints = config.get("formalization_hints", []) if isinstance(config, dict) else []
        preferred = config.get("preferred_problem_types", []) if isinstance(config, dict) else []
        hint_text = ", ".join(str(item) for item in hints[:2]) if hints else "기본 라이브러리 힌트"
        preferred_text = ", ".join(str(item) for item in preferred[:2]) if preferred else problem.domain
        weak_form = problem.weak_forms[0] if problem.weak_forms else problem.target
        weak_variant, explored_bound = self._counterexample_context(counterexample_report)
        reduction_statement = (
            weak_variant if isinstance(weak_variant, str) and weak_variant.strip() else weak_form
        )
        search_bound_text = (
            f"반례 탐색 상한 {explored_bound} 내에서 강한형 실패 가능성을 점검했다."
            if isinstance(explored_bound, int)
            else "반례 탐색 결과를 참조해 약화형 환원 경로를 정한다."
        )

        nodes = [
            ProofNode(
                node_id="n0",
                node_type="definition",
                title="정의와 표기 고정",
                statement=(
                    f"객체 {', '.join(problem.objects)} 와 표기 {', '.join(problem.notation_map.keys())} 를 고정한다."
                ),
                dependencies=[],
                status="ready",
            ),
            ProofNode(
                node_id="n1",
                node_type="lemma",
                title="도메인 분해 보조정리",
                statement=(
                    f"{preferred_text} 관점에서 가정 {', '.join(problem.assumptions)} 를 분해 가능한 하위 목표로 바꾼다. {search_bound_text}"
                ),
                dependencies=["n0"],
                status="candidate",
            ),
            ProofNode(
                node_id="n2",
                node_type="lemma",
                title="약화형 환원 경로",
                statement=(
                    f"약화형 '{reduction_statement}' 과 형식화 힌트 {hint_text} 를 연결하는 경로를 명시한다."
                ),
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
        return nodes

    def build(
        self,
        problem: NormalizedProblem,
        counterexample_report: CounterexampleReport | None = None,
    ) -> ProofDAG:
        metadata = problem.source_problem.get("metadata", {})
        spec = metadata.get("proof_search_spec", {}) if isinstance(metadata, dict) else {}
        if isinstance(spec, dict) and spec:
            nodes = self._spec_nodes(problem, spec)
            nodes = self._apply_counterexample_guidance(nodes, counterexample_report)
        else:
            nodes = self._derived_nodes(problem, counterexample_report)
        return self._write_dag(problem, nodes)
