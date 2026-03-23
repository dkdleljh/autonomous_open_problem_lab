from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path

from aopl.core.io_utils import append_jsonl, ensure_dir, now_utc_iso, write_json
from aopl.core.types import (
    BANNED_PROOF_PHRASES,
    CounterexampleReport,
    NormalizedProblem,
    ProofDAG,
    VerificationReport,
)


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


def _has_path(start: str, target: str, edges: list[tuple[str, str]]) -> bool:
    if start == target:
        return True
    adjacency: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        adjacency[src].append(dst)
    queue = deque([start])
    visited: set[str] = {start}
    while queue:
        node = queue.popleft()
        for nxt in adjacency.get(node, []):
            if nxt == target:
                return True
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    return False


class Verifier:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.audit_dir = ensure_dir(root / "data" / "audit_logs")
        self.report_dir = ensure_dir(root / "data" / "theorem_store")

    def _check_banned_phrases(self, dag: ProofDAG) -> list[str]:
        issues: list[str] = []
        for node in dag.nodes:
            for phrase in BANNED_PROOF_PHRASES:
                if phrase in node.statement:
                    issues.append(f"금지 표현 감지: {phrase} ({node.node_id})")
        return issues

    def _check_dag_integrity(self, dag: ProofDAG) -> list[str]:
        issues: list[str] = []
        node_ids = [node.node_id for node in dag.nodes]
        edge_pairs = [(edge["from"], edge["to"]) for edge in dag.edges]
        if not _is_dag(node_ids, edge_pairs):
            issues.append("proof DAG가 순환 구조를 가져 무결성이 깨졌습니다.")
        if not _has_path(dag.root_node, dag.target_node, edge_pairs):
            issues.append("proof DAG에서 루트와 목표 정리 사이의 경로가 없습니다.")
        return issues

    def _check_reference_conflict(self, problem: NormalizedProblem) -> list[str]:
        warnings: list[str] = []
        seen: set[str] = set()
        for source in problem.source_problem.get("sources", []):
            key = str(source.get("url", "")).strip()
            if key in seen:
                warnings.append(f"중복 참고문헌 URL 감지: {key}")
            seen.add(key)
        if not seen:
            warnings.append("참고문헌이 비어 있어 논문화 단계에서 차단될 수 있습니다.")
        return warnings

    def verify(
        self,
        problem: NormalizedProblem,
        dag: ProofDAG,
        counterexample_report: CounterexampleReport,
    ) -> VerificationReport:
        critical: list[str] = []
        warnings: list[str] = []

        critical.extend(self._check_banned_phrases(dag))
        critical.extend(self._check_dag_integrity(dag))
        warnings.extend(self._check_reference_conflict(problem))

        if (
            counterexample_report.found_counterexample
            and not counterexample_report.weak_variant_recommendation
        ):
            critical.append("강한형 반례가 발견되었지만 약화형 권고가 없어 진행할 수 없습니다.")

        passed = len(critical) == 0
        gate_reason = "검증 통과" if passed else "중대 이슈 발견으로 검증 실패"
        report = VerificationReport(
            problem_id=problem.problem_id,
            passed=passed,
            critical_issues=critical,
            warnings=warnings,
            counterexample_report=counterexample_report.to_dict(),
            gate_reason=gate_reason,
        )

        write_json(self.report_dir / f"{problem.problem_id}_verification.json", report.to_dict())
        append_jsonl(
            self.audit_dir / "verification_log.jsonl",
            {
                "problem_id": problem.problem_id,
                "timestamp": now_utc_iso(),
                "passed": passed,
                "critical_issues": critical,
                "warnings": warnings,
            },
        )
        return report
