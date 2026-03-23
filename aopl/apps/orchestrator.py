from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path
from typing import Any

from aopl.apps.counterexample_engine import CounterexampleEngine
from aopl.apps.formalizer import Formalizer
from aopl.apps.harvester import Harvester
from aopl.apps.normalizer import Normalizer
from aopl.apps.paper_generator import PaperGenerator
from aopl.apps.proof_engine import ProofEngine
from aopl.apps.registry import Registry
from aopl.apps.scorer import Scorer
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.apps.verifier import Verifier
from aopl.core.io_utils import append_jsonl, ensure_dir, now_utc_iso, read_yaml, write_json
from aopl.core.state_machine import StageMachine
from aopl.core.types import PipelineStage, StageEvent


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


class Orchestrator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.harvester = Harvester(root)
        self.registry = Registry(root)
        self.normalizer = Normalizer(root)
        self.scorer = Scorer(root)
        self.counterexample_engine = CounterexampleEngine(root)
        self.proof_engine = ProofEngine(root)
        self.verifier = Verifier(root)
        self.formalizer = Formalizer(root)
        self.paper_generator = PaperGenerator(root)
        self.submission_builder = SubmissionBuilder(root)
        self.stage_machine = StageMachine()
        self.audit_log_file = ensure_dir(root / "data" / "audit_logs") / "pipeline_audit.jsonl"
        self.runtime_config = read_yaml(root / "configs" / "global" / "runtime.yaml", default={})

    def _event(
        self,
        problem_id: str,
        stage: PipelineStage,
        gate_name: str,
        passed: bool,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = StageEvent(
            problem_id=problem_id,
            stage=stage,
            gate_name=gate_name,
            passed=passed,
            reason=reason,
            timestamp=now_utc_iso(),
            metadata=metadata or {},
        )
        append_jsonl(self.audit_log_file, event.to_dict())

    def _harvest_gate(self, sources: list[dict[str, Any]]) -> tuple[bool, str, dict[str, Any]]:
        min_reliability = (
            self.runtime_config.get("gates", {}).get("harvest_min_reliability", 0.75)
            if isinstance(self.runtime_config, dict)
            else 0.75
        )
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

    def _normalize_gate(self, normalized: dict[str, Any]) -> tuple[bool, str]:
        has_objects = bool(normalized.get("objects"))
        has_assumptions = bool(normalized.get("assumptions"))
        has_target = bool(normalized.get("target"))
        if has_objects and has_assumptions and has_target:
            return True, "Normalize Gate 통과"
        return False, "정의, 가정, 목표 분리 실패"

    def _proof_integrity_gate(self, dag_dict: dict[str, Any]) -> tuple[bool, str]:
        edge_pairs: list[tuple[str, str]] = []
        for edge in dag_dict.get("edges", []):
            edge_pairs.append((edge["from"], edge["to"]))
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

    def _formalization_gate(self, unresolved_count: int) -> tuple[bool, str]:
        threshold_file = self.root / "configs" / "formalization" / "obligation_thresholds.yaml"
        threshold_config = read_yaml(threshold_file, default={})
        max_allowed = 12
        if isinstance(threshold_config, dict):
            max_allowed = int(threshold_config.get("max_unresolved_obligations", 12))
        if unresolved_count > max_allowed:
            return False, "미해결 obligation 과다로 Formalization Gate 보류"
        return True, "Formalization Gate 통과"

    def _release_gate(self, submission_dict: dict[str, Any]) -> tuple[bool, str]:
        required = ["package_file", "source_bundle_file", "checksum_file", "release_notes_file"]
        for key in required:
            value = submission_dict.get(key)
            if not value:
                return False, f"Release Gate 실패: {key} 누락"
            if not (self.root / value).exists():
                return False, f"Release Gate 실패: {value} 파일 누락"
        return True, "Release Gate 통과"

    def run(self, limit: int | None = None) -> dict[str, Any]:
        harvested_candidates = self.harvester.harvest()
        records = self.registry.register(harvested_candidates)
        if limit is not None:
            records = records[:limit]

        run_summary: dict[str, Any] = {"processed": [], "blocked": []}
        for record in records:
            current_stage = PipelineStage.REGISTERED

            harvest_passed, harvest_reason, harvest_meta = self._harvest_gate(record.sources)
            self._event(
                record.problem_id,
                current_stage,
                "Harvest Gate",
                harvest_passed,
                harvest_reason,
                harvest_meta,
            )
            transition = self.stage_machine.transition(
                current_stage, harvest_passed, harvest_reason
            )
            if transition.blocked:
                self.registry.update_status(
                    record.problem_id, PipelineStage.BLOCKED, harvest_reason
                )
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": harvest_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, harvest_reason)

            normalized = self.normalizer.normalize(record)
            normalize_passed, normalize_reason = self._normalize_gate(normalized.to_dict())
            self._event(
                record.problem_id,
                current_stage,
                "Normalize Gate",
                normalize_passed,
                normalize_reason,
            )
            transition = self.stage_machine.transition(
                current_stage, normalize_passed, normalize_reason
            )
            if transition.blocked:
                self.registry.update_status(
                    record.problem_id, PipelineStage.BLOCKED, normalize_reason
                )
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": normalize_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, normalize_reason)

            score = self.scorer.score(normalized)
            score_passed = score.selected
            score_reason = "점수 임계값 통과" if score.selected else "점수 임계값 미달"
            self._event(
                record.problem_id,
                current_stage,
                "Score Gate",
                score_passed,
                score_reason,
                score.to_dict(),
            )
            transition = self.stage_machine.transition(current_stage, score_passed, score_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, score_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": score_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, score_reason)

            counterexample_report = self.counterexample_engine.run(normalized)
            counterexample_reason = "Counterexample Gate 통과"
            if counterexample_report.found_counterexample:
                if counterexample_report.weak_variant_recommendation:
                    counterexample_reason = "강한형 반례 발견, 약화형으로 자동 전환"
                else:
                    counterexample_reason = "강한형 반례 발견, 약화형 권고 누락"
            counterexample_passed = not (
                counterexample_report.found_counterexample
                and not counterexample_report.weak_variant_recommendation
            )
            self._event(
                record.problem_id,
                current_stage,
                "Counterexample Gate",
                counterexample_passed,
                counterexample_reason,
                counterexample_report.to_dict(),
            )
            transition = self.stage_machine.transition(
                current_stage, counterexample_passed, counterexample_reason
            )
            if transition.blocked:
                self.registry.update_status(
                    record.problem_id, PipelineStage.BLOCKED, counterexample_reason
                )
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": counterexample_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, counterexample_reason)

            dag = self.proof_engine.build(normalized)
            proof_passed, proof_reason = self._proof_integrity_gate(dag.to_dict())
            self._event(
                record.problem_id, current_stage, "Proof Integrity Gate", proof_passed, proof_reason
            )
            transition = self.stage_machine.transition(current_stage, proof_passed, proof_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, proof_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": proof_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, proof_reason)

            draft_reason = "proof 초안 생성 완료"
            self._event(record.problem_id, current_stage, "Draft Gate", True, draft_reason)
            transition = self.stage_machine.transition(current_stage, True, draft_reason)
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, draft_reason)

            verification = self.verifier.verify(normalized, dag, counterexample_report)
            verify_reason = verification.gate_reason
            self._event(
                record.problem_id,
                current_stage,
                "Verification Gate",
                verification.passed,
                verify_reason,
                verification.to_dict(),
            )
            transition = self.stage_machine.transition(
                current_stage, verification.passed, verify_reason
            )
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, verify_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": verify_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, verify_reason)

            formal_report = self.formalizer.generate(normalized, dag)
            formal_passed, formal_reason = self._formalization_gate(
                len(formal_report.obligations_unresolved)
            )
            self._event(
                record.problem_id,
                current_stage,
                "Formalization Gate",
                formal_passed,
                formal_reason,
                formal_report.to_dict(),
            )
            transition = self.stage_machine.transition(current_stage, formal_passed, formal_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, formal_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": formal_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, formal_reason)

            paper_manifest = self.paper_generator.generate(
                normalized, dag, verification, formal_report
            )
            self._event(
                record.problem_id, current_stage, "Paper Draft Gate", True, "논문 초안 생성 완료"
            )
            transition = self.stage_machine.transition(current_stage, True, "논문 초안 생성 완료")
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, "논문 초안 생성 완료")

            paper_passed, paper_reason = self.paper_generator.qa_check(paper_manifest)
            self._event(
                record.problem_id, current_stage, "Paper QA Gate", paper_passed, paper_reason
            )
            transition = self.stage_machine.transition(current_stage, paper_passed, paper_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, paper_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": paper_reason}
                )
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, paper_reason)

            submission_manifest = self.submission_builder.build(paper_manifest)
            self._event(
                record.problem_id, current_stage, "Submission Gate", True, "제출 패키지 생성 완료"
            )
            transition = self.stage_machine.transition(current_stage, True, "제출 패키지 생성 완료")
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, "제출 패키지 생성 완료")

            release_passed, release_reason = self._release_gate(submission_manifest.to_dict())
            self._event(
                record.problem_id, current_stage, "Release Gate", release_passed, release_reason
            )
            transition = self.stage_machine.transition(
                current_stage, release_passed, release_reason
            )
            if transition.blocked:
                self.registry.update_status(
                    record.problem_id, PipelineStage.BLOCKED, release_reason
                )
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": release_reason}
                )
                continue
            current_stage = PipelineStage.RELEASED
            self.registry.update_status(record.problem_id, current_stage, release_reason)

            run_summary["processed"].append(
                {
                    "problem_id": record.problem_id,
                    "final_stage": current_stage.value,
                    "score": score.score,
                    "paper_manifest": asdict(paper_manifest),
                    "submission_manifest": asdict(submission_manifest),
                }
            )

        summary_path = self.root / "data" / "audit_logs" / "last_run_summary.json"
        write_json(summary_path, run_summary)
        return run_summary
