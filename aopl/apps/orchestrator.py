from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from aopl.apps.harvester import Harvester
from aopl.apps.normalizer import Normalizer
from aopl.apps.registry import Registry
from aopl.apps.scorer import Scorer
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.apps.verifier import Verifier
from aopl.core.config_store import ConfigStore
from aopl.core.gates import GatePolicy
from aopl.core.io_utils import append_jsonl, ensure_dir, now_utc_iso, read_yaml, write_json
from aopl.core.schema_utils import validate_schema
from aopl.core.state_machine import StageMachine
from aopl.core.types import PipelineStage, StageEvent
from aopl.services.engine_factory import EngineFactory


class Orchestrator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.harvester = Harvester(root)
        self.registry = Registry(root)
        self.normalizer = Normalizer(root)
        self.scorer = Scorer(root)
        self.verifier = Verifier(root)
        self.submission_builder = SubmissionBuilder(root)
        self.stage_machine = StageMachine()
        self.audit_log_file = ensure_dir(root / "data" / "audit_logs") / "pipeline_audit.jsonl"
        self.config_store = ConfigStore(root)
        self.runtime_config = self.config_store.runtime()
        self.gates = GatePolicy(root, self.runtime_config)
        engine_factory = EngineFactory(root, self.runtime_config)
        self.engine_backends = engine_factory.backend_summary()
        self.counterexample_engine = engine_factory.counterexample_engine()
        self.proof_engine = engine_factory.proof_engine()
        self.formalizer = engine_factory.formalizer()
        self.paper_generator = engine_factory.paper_generator()

    def _provenance_metadata(self, record: Any) -> dict[str, Any]:
        provenance = record.metadata.get("provenance", {}) if hasattr(record, "metadata") else {}
        if not isinstance(provenance, dict):
            provenance = {}
        return {
            "harvest_batch_id": provenance.get("harvest_batch_id"),
            "harvested_at": provenance.get("harvested_at"),
            "source_signature": provenance.get("source_signature"),
            "candidate_hash": provenance.get("candidate_hash"),
        }

    def _verification_metadata(self, verification: Any) -> dict[str, Any]:
        return {
            "verification_passed": verification.passed,
            "verification_gate_reason": verification.gate_reason,
            "critical_issue_count": len(verification.critical_issues),
            "warning_count": len(verification.warnings),
        }

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
        payload = event.to_dict()
        validate_schema(self.root, "stage_event_schema", payload)
        append_jsonl(self.audit_log_file, payload)

    def run(self, limit: int | None = None) -> dict[str, Any]:
        harvested_candidates = self.harvester.harvest()
        records = self.registry.register(harvested_candidates)
        if limit is not None:
            records = records[:limit]

        run_summary: dict[str, Any] = {
            "engine_backends": dict(self.engine_backends),
            "stats": {
                "total_records": len(records),
                "processed_count": 0,
                "blocked_count": 0,
                "released_problem_ids": [],
                "verification_critical_issue_total": 0,
                "verification_warning_total": 0,
            },
            "processed": [],
            "blocked": [],
        }
        for record in records:
            current_stage = PipelineStage.REGISTERED
            base_metadata = self._provenance_metadata(record)

            harvest_passed, harvest_reason, harvest_meta = self.gates.harvest(record.sources)
            self._event(
                record.problem_id,
                current_stage,
                "Harvest Gate",
                harvest_passed,
                harvest_reason,
                {**base_metadata, **harvest_meta},
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
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, harvest_reason)

            normalized = self.normalizer.normalize(record)
            normalize_passed, normalize_reason = self.gates.normalize(normalized.to_dict())
            self._event(
                record.problem_id,
                current_stage,
                "Normalize Gate",
                normalize_passed,
                normalize_reason,
                base_metadata,
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
                run_summary["stats"]["blocked_count"] += 1
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
                {**base_metadata, **score.to_dict()},
            )
            transition = self.stage_machine.transition(current_stage, score_passed, score_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, score_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": score_reason}
                )
                run_summary["stats"]["blocked_count"] += 1
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
                {**base_metadata, **counterexample_report.to_dict()},
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
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, counterexample_reason)

            dag = self.proof_engine.build(normalized, counterexample_report)
            proof_passed, proof_reason = self.gates.proof_integrity(dag.to_dict())
            self._event(
                record.problem_id,
                current_stage,
                "Proof Integrity Gate",
                proof_passed,
                proof_reason,
                {
                    **base_metadata,
                    "proof_backend": dag.backend,
                    "proof_node_count": len(dag.nodes),
                    "proof_edge_count": len(dag.edges),
                },
            )
            transition = self.stage_machine.transition(current_stage, proof_passed, proof_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, proof_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": proof_reason}
                )
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, proof_reason)

            draft_reason = "proof 초안 생성 완료"
            self._event(
                record.problem_id,
                current_stage,
                "Draft Gate",
                True,
                draft_reason,
                {**base_metadata, "proof_backend": dag.backend},
            )
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
                {**base_metadata, **verification.to_dict(), **self._verification_metadata(verification)},
            )
            transition = self.stage_machine.transition(
                current_stage, verification.passed, verify_reason
            )
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, verify_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": verify_reason}
                )
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, verify_reason)

            formal_report = self.formalizer.generate(normalized, dag)
            formal_passed, formal_reason = self.gates.formalization(
                len(formal_report.obligations_unresolved)
            )
            self._event(
                record.problem_id,
                current_stage,
                "Formalization Gate",
                formal_passed,
                formal_reason,
                {**base_metadata, **self._verification_metadata(verification), **formal_report.to_dict()},
            )
            transition = self.stage_machine.transition(current_stage, formal_passed, formal_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, formal_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": formal_reason}
                )
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, formal_reason)

            paper_manifest = self.paper_generator.generate(
                normalized, dag, verification, formal_report
            )
            self._event(
                record.problem_id,
                current_stage,
                "Paper Draft Gate",
                True,
                "논문 초안 생성 완료",
                {
                    **base_metadata,
                    **self._verification_metadata(verification),
                    "paper_backend": paper_manifest.backend,
                    "pdf_artifact_kind": paper_manifest.pdf_artifact_kind,
                },
            )
            transition = self.stage_machine.transition(current_stage, True, "논문 초안 생성 완료")
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, "논문 초안 생성 완료")

            paper_passed, paper_reason = self.paper_generator.qa_check(paper_manifest)
            self._event(
                record.problem_id,
                current_stage,
                "Paper QA Gate",
                paper_passed,
                paper_reason,
                {
                    **base_metadata,
                    **self._verification_metadata(verification),
                    "paper_backend": paper_manifest.backend,
                    "pdf_artifact_kind": paper_manifest.pdf_artifact_kind,
                },
            )
            transition = self.stage_machine.transition(current_stage, paper_passed, paper_reason)
            if transition.blocked:
                self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, paper_reason)
                run_summary["blocked"].append(
                    {"problem_id": record.problem_id, "reason": paper_reason}
                )
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, paper_reason)

            submission_manifest = self.submission_builder.build(
                paper_manifest, verification, formal_report
            )
            self._event(
                record.problem_id,
                current_stage,
                "Submission Gate",
                True,
                "제출 패키지 생성 완료",
                {
                    **base_metadata,
                    **submission_manifest.verification_summary,
                    "release_notes_file": submission_manifest.release_notes_file,
                    "package_file": submission_manifest.package_file,
                },
            )
            transition = self.stage_machine.transition(current_stage, True, "제출 패키지 생성 완료")
            current_stage = transition.next_stage
            self.registry.update_status(record.problem_id, current_stage, "제출 패키지 생성 완료")

            release_passed, release_reason = self.gates.release(
                submission_manifest.to_dict(),
                paper_manifest.to_dict(),
                record.metadata,
                verification.to_dict(),
                formal_report.to_dict(),
            )
            self._event(
                record.problem_id,
                current_stage,
                "Release Gate",
                release_passed,
                release_reason,
                {
                    **base_metadata,
                    **submission_manifest.verification_summary,
                    "release_notes_file": submission_manifest.release_notes_file,
                    "package_file": submission_manifest.package_file,
                    "paper_pdf_artifact_kind": paper_manifest.pdf_artifact_kind,
                    "formalization_artifact_kind": formal_report.artifact_kind,
                },
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
                run_summary["stats"]["blocked_count"] += 1
                continue
            current_stage = PipelineStage.RELEASED
            self.registry.update_status(record.problem_id, current_stage, release_reason)
            run_summary["stats"]["processed_count"] += 1
            run_summary["stats"]["released_problem_ids"].append(record.problem_id)
            run_summary["stats"]["verification_critical_issue_total"] += len(
                verification.critical_issues
            )
            run_summary["stats"]["verification_warning_total"] += len(verification.warnings)

            run_summary["processed"].append(
                {
                    "problem_id": record.problem_id,
                    "final_stage": current_stage.value,
                    "score": score.score,
                    "provenance_summary": {
                        "harvest_batch_id": record.metadata.get("provenance", {}).get(
                            "harvest_batch_id"
                        ),
                        "harvested_at": record.metadata.get("provenance", {}).get("harvested_at"),
                        "source_signature": record.metadata.get("provenance", {}).get(
                            "source_signature"
                        ),
                        "candidate_hash": record.metadata.get("provenance", {}).get(
                            "candidate_hash"
                        ),
                    },
                    "backend_summary": {
                        **verification.backend_summary,
                        "formalizer": formal_report.backend,
                        "paper_generator": paper_manifest.backend,
                    },
                    "artifact_summary": {
                        "formalization_artifact_kind": formal_report.artifact_kind,
                        "paper_pdf_artifact_kind": paper_manifest.pdf_artifact_kind,
                        "paper_pdf_build_success": paper_manifest.pdf_build_success,
                    },
                    "verification_summary": submission_manifest.verification_summary,
                    "verification": verification.to_dict(),
                    "formalization_report": formal_report.to_dict(),
                    "paper_manifest": asdict(paper_manifest),
                    "submission_manifest": asdict(submission_manifest),
                }
            )

        summary_path = self.root / "data" / "audit_logs" / "last_run_summary.json"
        validate_schema(self.root, "run_summary_schema", run_summary)
        write_json(summary_path, run_summary)
        return run_summary
