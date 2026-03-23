from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from aopl.core.config_store import ConfigStore


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


class GatePolicy:
    def __init__(self, root: Path, runtime_config: dict[str, Any] | None = None) -> None:
        self.root = root
        self.config_store = ConfigStore(root)
        self.runtime_config = self.config_store.runtime(runtime_config)

    def _release_policy(self) -> dict[str, Any]:
        release_policy = self.runtime_config.get("release", {})
        return release_policy if isinstance(release_policy, dict) else {}

    def harvest(self, sources: list[dict[str, Any]]) -> tuple[bool, str, dict[str, Any]]:
        min_reliability = self.runtime_config.get("gates", {}).get("harvest_min_reliability", 0.75)
        reliabilities = [float(source.get("reliability", 0.0)) for source in sources]
        if not reliabilities:
            return False, "출처가 없어 Harvest Gate 실패", {"average_reliability": 0.0}
        avg = sum(reliabilities) / len(reliabilities)
        if avg < min_reliability:
            return (
                False,
                "출처 신뢰도 임계값 미달",
                {"average_reliability": avg, "threshold": min_reliability},
            )
        return True, "Harvest Gate 통과", {"average_reliability": avg, "threshold": min_reliability}

    def normalize(self, normalized: dict[str, Any]) -> tuple[bool, str]:
        has_objects = bool(normalized.get("objects"))
        has_assumptions = bool(normalized.get("assumptions"))
        has_target = bool(normalized.get("target"))
        if has_objects and has_assumptions and has_target:
            return True, "Normalize Gate 통과"
        return False, "정의, 가정, 목표 분리 실패"

    def proof_integrity(self, dag_dict: dict[str, Any]) -> tuple[bool, str]:
        edge_pairs = [(edge["from"], edge["to"]) for edge in dag_dict.get("edges", [])]
        root_node = dag_dict.get("root_node")
        target_node = dag_dict.get("target_node")
        node_ids = [
            node.get("node_id") for node in dag_dict.get("nodes", []) if isinstance(node, dict)
        ]
        node_ids = [node_id for node_id in node_ids if isinstance(node_id, str)]
        if root_node is None or target_node is None:
            return False, "proof DAG 루트 또는 목표 노드 누락"
        if not _is_dag(node_ids, edge_pairs):
            return False, "proof DAG 순환 감지"
        if not _has_path(root_node, target_node, edge_pairs):
            return False, "proof DAG 단절"
        return True, "Proof Integrity Gate 통과"

    def formalization(self, unresolved_count: int) -> tuple[bool, str]:
        threshold_config = self.config_store.obligation_thresholds()
        max_allowed = 12
        if isinstance(threshold_config, dict):
            max_allowed = int(threshold_config.get("max_unresolved_obligations", 12))
        if unresolved_count > max_allowed:
            return False, "미해결 obligation 과다로 Formalization Gate 보류"
        return True, "Formalization Gate 통과"

    def release(
        self,
        submission_dict: dict[str, Any],
        paper_manifest_dict: dict[str, Any],
        record_metadata: dict[str, Any],
        verification_dict: dict[str, Any],
        formal_report_dict: dict[str, Any],
    ) -> tuple[bool, str]:
        required = ["package_file", "source_bundle_file", "checksum_file", "release_notes_file"]
        for key in required:
            value = submission_dict.get(key)
            if not value:
                return False, f"Release Gate 실패: {key} 누락"
            if not (self.root / value).exists():
                return False, f"Release Gate 실패: {value} 파일 누락"
        release_policy = self._release_policy()
        if not bool(release_policy.get("allow_demo_release", False)) and bool(
            record_metadata.get("demo_mode", False)
        ):
            return False, "Release Gate 실패: demo 문제는 기본 정책에서 릴리즈 금지"
        if bool(release_policy.get("require_verification_pass", True)) and not bool(
            verification_dict.get("passed", False)
        ):
            return False, "Release Gate 실패: 검증 미통과"
        if bool(release_policy.get("require_formal_build_success", True)) and not bool(
            formal_report_dict.get("build_success", False)
        ):
            return False, "Release Gate 실패: 형식화 빌드 성공 필요"
        if bool(release_policy.get("require_pdf_build_success", True)) and not bool(
            paper_manifest_dict.get("pdf_build_success", False)
        ):
            return False, "Release Gate 실패: 논문 PDF 빌드 성공 필요"
        if bool(release_policy.get("require_pdf_build_success", True)) and (
            paper_manifest_dict.get("pdf_artifact_kind") == "placeholder_pdf"
        ):
            return False, "Release Gate 실패: placeholder PDF는 릴리즈 불가"
        threshold_config = self.config_store.obligation_thresholds()
        max_allowed = 8
        if isinstance(threshold_config, dict):
            max_allowed = int(threshold_config.get("max_unresolved_for_release", 8))
        unresolved = formal_report_dict.get("obligations_unresolved", [])
        unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0
        if unresolved_count > max_allowed:
            return False, "Release Gate 실패: 릴리즈 허용 미해결 obligation 초과"
        return True, "Release Gate 통과"
