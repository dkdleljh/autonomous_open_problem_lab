from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import time
from typing import Any, Callable

from aopl.apps.harvester import Harvester
from aopl.apps.normalizer import Normalizer
from aopl.apps.registry import Registry
from aopl.apps.scorer import Scorer
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.apps.verifier import Verifier
from aopl.core.config_store import ConfigStore
from aopl.core.gates import GatePolicy
from aopl.core.io_utils import append_jsonl, ensure_dir, now_utc_iso, parse_utc_iso, write_json
from aopl.core.schema_utils import validate_schema
from aopl.core.state_machine import StageMachine
from aopl.core.types import PipelineStage, StageEvent
from aopl.services.engine_factory import EngineFactory


class StageExecutionError(RuntimeError):
    def __init__(self, stage_name: str, cause: Exception, failure_class: str, attempts: int) -> None:
        super().__init__(str(cause))
        self.stage_name = stage_name
        self.cause = cause
        self.failure_class = failure_class
        self.attempts = attempts


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

    def _max_retry_per_stage(self) -> int:
        value = self.runtime_config.get("max_retry_per_stage", 0)
        if isinstance(value, int) and value >= 0:
            return value
        return 0

    def _retry_backoff_seconds(self) -> int:
        queue_config = self.config_store.queue()
        retry_policy = queue_config.get("retry_policy", {}) if isinstance(queue_config, dict) else {}
        if isinstance(retry_policy, dict):
            value = retry_policy.get("backoff_seconds", 0)
            if isinstance(value, int) and value >= 0:
                return value
        return 0

    def _transient_failure_escalation_threshold(self) -> int:
        value = self.runtime_config.get("transient_failure_escalation_threshold", 3)
        if isinstance(value, int) and value >= 1:
            return value
        return 3

    def _transient_failure_lookback_days(self) -> int:
        value = self.runtime_config.get("transient_failure_lookback_days", 7)
        if isinstance(value, int) and value >= 1:
            return value
        return 7

    def _stage_transient_failure_threshold(self, stage_name: str) -> int:
        stage_thresholds = self.runtime_config.get("transient_failure_stage_thresholds", {})
        if isinstance(stage_thresholds, dict):
            value = stage_thresholds.get(stage_name)
            if isinstance(value, int) and value >= 1:
                return value
        return self._transient_failure_escalation_threshold()

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

    def _classify_failure(self, error: Exception) -> str:
        if isinstance(error, (ValueError, TypeError, KeyError)):
            return "permanent"
        if isinstance(error, (TimeoutError, FileNotFoundError, OSError, RuntimeError)):
            return "transient"
        return "unknown"

    def _historical_transient_retry_count(
        self,
        problem_id: str,
        stage_name: str,
        current_stage: PipelineStage,
    ) -> int:
        if not self.audit_log_file.exists():
            return 0
        count = 0
        now = parse_utc_iso(now_utc_iso())
        lookback_days = self._transient_failure_lookback_days()
        for line in self.audit_log_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("problem_id") != problem_id:
                continue
            if payload.get("stage") != current_stage.value:
                continue
            if payload.get("gate_name") != f"{stage_name} Retry":
                continue
            timestamp = payload.get("timestamp")
            if isinstance(timestamp, str) and now is not None:
                parsed = parse_utc_iso(timestamp)
                if parsed is None:
                    continue
                elapsed = now - parsed
                if elapsed.total_seconds() > lookback_days * 86400:
                    continue
            metadata = payload.get("metadata", {})
            if isinstance(metadata, dict) and metadata.get("failure_class") == "transient":
                count += 1
        return count

    def _run_with_retry(
        self,
        func: Callable[[], Any],
        record: Any,
        current_stage: PipelineStage,
        stage_name: str,
    ) -> tuple[Any, int, str | None]:
        max_retry = self._max_retry_per_stage()
        attempts = 0
        while True:
            attempts += 1
            try:
                return func(), attempts, None
            except Exception as error:
                failure_class = self._classify_failure(error)
                historical_transient_count = self._historical_transient_retry_count(
                    record.problem_id, stage_name, current_stage
                )
                threshold = self._stage_transient_failure_threshold(stage_name)
                escalated = (
                    failure_class == "transient"
                    and historical_transient_count + 1 >= threshold
                )
                if escalated:
                    failure_class = "permanent"
                self._event(
                    record.problem_id,
                    current_stage,
                    f"{stage_name} Retry",
                    False,
                    f"{stage_name} 실행 예외: {error}",
                    {
                        **self._provenance_metadata(record),
                        "attempt": attempts,
                        "max_retry_per_stage": max_retry,
                        "exception_type": error.__class__.__name__,
                        "failure_class": failure_class,
                        "historical_transient_count": historical_transient_count,
                        "escalated_from_transient": escalated,
                        "transient_failure_escalation_threshold": threshold,
                        "backoff_seconds": self._retry_backoff_seconds(),
                    },
                )
                if failure_class == "permanent" or attempts > max_retry:
                    raise StageExecutionError(stage_name, error, failure_class, attempts) from error
                backoff_seconds = self._retry_backoff_seconds()
                if backoff_seconds > 0:
                    time.sleep(backoff_seconds)

    def _block_record(
        self,
        run_summary: dict[str, Any],
        record: Any,
        current_stage: PipelineStage,
        reason: str,
        gate_name: str = "Runtime Safety Gate",
        extra_metadata: dict[str, Any] | None = None,
        failure_class: str = "unknown",
        retry_count: int = 0,
    ) -> None:
        metadata = {
            **self._provenance_metadata(record),
            **(extra_metadata or {}),
            "failure_class": failure_class,
            "retry_count": retry_count,
        }
        self._event(
            record.problem_id,
            current_stage,
            gate_name,
            False,
            reason,
            metadata,
        )
        self.registry.update_status(record.problem_id, PipelineStage.BLOCKED, reason)
        run_summary["blocked"].append(
            {
                "problem_id": record.problem_id,
                "reason": reason,
                "stage": current_stage.value,
                "failure_class": failure_class,
                "retry_count": retry_count,
            }
        )
        run_summary["stats"]["blocked_count"] += 1

    def _write_incident_summary(self, run_summary: dict[str, Any]) -> None:
        blocked = run_summary.get("blocked", [])
        reasons: dict[str, int] = {}
        runtime_exception_count = 0
        failure_classes: dict[str, int] = {}
        for item in blocked:
            reason = str(item.get("reason", "unknown"))
            reasons[reason] = reasons.get(reason, 0) + 1
            if "런타임 예외" in reason:
                runtime_exception_count += 1
            failure_class = str(item.get("failure_class", "unknown"))
            failure_classes[failure_class] = failure_classes.get(failure_class, 0) + 1
        payload = {
            "generated_at": now_utc_iso(),
            "total_records": run_summary["stats"]["total_records"],
            "processed_count": run_summary["stats"]["processed_count"],
            "blocked_count": run_summary["stats"]["blocked_count"],
            "runtime_exception_count": runtime_exception_count,
            "failure_class_summary": failure_classes,
            "policy_context": {
                "max_retry_per_stage": self._max_retry_per_stage(),
                "retry_backoff_seconds": self._retry_backoff_seconds(),
                "transient_failure_lookback_days": self._transient_failure_lookback_days(),
                "default_transient_failure_escalation_threshold": self._transient_failure_escalation_threshold(),
                "stage_transient_failure_thresholds": (
                    self.runtime_config.get("transient_failure_stage_thresholds", {})
                    if isinstance(self.runtime_config.get("transient_failure_stage_thresholds", {}), dict)
                    else {}
                ),
            },
            "top_block_reasons": [
                {"reason": reason, "count": count}
                for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
            ],
        }
        write_json(self.root / "data" / "audit_logs" / "last_incident_summary.json", payload)

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
            try:
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
                    self._block_record(
                        run_summary, record, current_stage, harvest_reason, "Harvest Gate"
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, harvest_reason)

                normalized, normalize_attempts, _ = self._run_with_retry(
                    lambda: self.normalizer.normalize(record),
                    record,
                    current_stage,
                    "Normalize",
                )
                normalize_passed, normalize_reason = self.gates.normalize(normalized.to_dict())
                self._event(
                    record.problem_id,
                    current_stage,
                    "Normalize Gate",
                    normalize_passed,
                    normalize_reason,
                    {**base_metadata, "attempts": normalize_attempts},
                )
                transition = self.stage_machine.transition(
                    current_stage, normalize_passed, normalize_reason
                )
                if transition.blocked:
                    self._block_record(
                        run_summary, record, current_stage, normalize_reason, "Normalize Gate"
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, normalize_reason)

                score, score_attempts, _ = self._run_with_retry(
                    lambda: self.scorer.score(normalized),
                    record,
                    current_stage,
                    "Score",
                )
                score_passed = score.selected
                score_reason = "점수 임계값 통과" if score.selected else "점수 임계값 미달"
                self._event(
                    record.problem_id,
                    current_stage,
                    "Score Gate",
                    score_passed,
                    score_reason,
                    {**base_metadata, **score.to_dict(), "attempts": score_attempts},
                )
                transition = self.stage_machine.transition(current_stage, score_passed, score_reason)
                if transition.blocked:
                    self._block_record(
                        run_summary, record, current_stage, score_reason, "Score Gate"
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, score_reason)

                counterexample_report, counterexample_attempts, _ = self._run_with_retry(
                    lambda: self.counterexample_engine.run(normalized),
                    record,
                    current_stage,
                    "Counterexample",
                )
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
                    {
                        **base_metadata,
                        **counterexample_report.to_dict(),
                        "attempts": counterexample_attempts,
                    },
                )
                transition = self.stage_machine.transition(
                    current_stage, counterexample_passed, counterexample_reason
                )
                if transition.blocked:
                    self._block_record(
                        run_summary,
                        record,
                        current_stage,
                        counterexample_reason,
                        "Counterexample Gate",
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, counterexample_reason)

                dag, proof_attempts, _ = self._run_with_retry(
                    lambda: self.proof_engine.build(normalized, counterexample_report),
                    record,
                    current_stage,
                    "Proof",
                )
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
                        "attempts": proof_attempts,
                    },
                )
                transition = self.stage_machine.transition(current_stage, proof_passed, proof_reason)
                if transition.blocked:
                    self._block_record(
                        run_summary, record, current_stage, proof_reason, "Proof Integrity Gate"
                    )
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

                verification, verification_attempts, _ = self._run_with_retry(
                    lambda: self.verifier.verify(normalized, dag, counterexample_report),
                    record,
                    current_stage,
                    "Verification",
                )
                verify_reason = verification.gate_reason
                self._event(
                    record.problem_id,
                    current_stage,
                    "Verification Gate",
                    verification.passed,
                    verify_reason,
                    {
                        **base_metadata,
                        **verification.to_dict(),
                        **self._verification_metadata(verification),
                        "attempts": verification_attempts,
                    },
                )
                transition = self.stage_machine.transition(
                    current_stage, verification.passed, verify_reason
                )
                if transition.blocked:
                    self._block_record(
                        run_summary, record, current_stage, verify_reason, "Verification Gate"
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, verify_reason)

                formal_report, formalization_attempts, _ = self._run_with_retry(
                    lambda: self.formalizer.generate(normalized, dag),
                    record,
                    current_stage,
                    "Formalization",
                )
                formal_passed, formal_reason = self.gates.formalization(
                    len(formal_report.obligations_unresolved)
                )
                self._event(
                    record.problem_id,
                    current_stage,
                    "Formalization Gate",
                    formal_passed,
                    formal_reason,
                    {
                        **base_metadata,
                        **self._verification_metadata(verification),
                        **formal_report.to_dict(),
                        "attempts": formalization_attempts,
                    },
                )
                transition = self.stage_machine.transition(
                    current_stage, formal_passed, formal_reason
                )
                if transition.blocked:
                    self._block_record(
                        run_summary, record, current_stage, formal_reason, "Formalization Gate"
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, formal_reason)

                paper_manifest, paper_attempts, _ = self._run_with_retry(
                    lambda: self.paper_generator.generate(
                        normalized, dag, verification, formal_report
                    ),
                    record,
                    current_stage,
                    "Paper",
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
                        "attempts": paper_attempts,
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
                transition = self.stage_machine.transition(
                    current_stage, paper_passed, paper_reason
                )
                if transition.blocked:
                    self._block_record(
                        run_summary, record, current_stage, paper_reason, "Paper QA Gate"
                    )
                    continue
                current_stage = transition.next_stage
                self.registry.update_status(record.problem_id, current_stage, paper_reason)

                submission_manifest, submission_attempts, _ = self._run_with_retry(
                    lambda: self.submission_builder.build(
                        paper_manifest, verification, formal_report
                    ),
                    record,
                    current_stage,
                    "Submission",
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
                        "attempts": submission_attempts,
                    },
                )
                transition = self.stage_machine.transition(
                    current_stage, True, "제출 패키지 생성 완료"
                )
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
                    self._block_record(
                        run_summary, record, current_stage, release_reason, "Release Gate"
                    )
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
            except StageExecutionError as error:
                reason = f"런타임 예외로 문제 처리 중단: {error}"
                self._block_record(
                    run_summary,
                    record,
                    current_stage,
                    reason,
                    "Runtime Safety Gate",
                    {
                        "exception_type": error.cause.__class__.__name__,
                        "stage_name": error.stage_name,
                    },
                    failure_class=error.failure_class,
                    retry_count=error.attempts,
                )
                continue
            except Exception as error:
                reason = f"런타임 예외로 문제 처리 중단: {error}"
                failure_class = self._classify_failure(error)
                self._block_record(
                    run_summary,
                    record,
                    current_stage,
                    reason,
                    "Runtime Safety Gate",
                    {"exception_type": error.__class__.__name__},
                    failure_class=failure_class,
                )
                continue

        summary_path = self.root / "data" / "audit_logs" / "last_run_summary.json"
        validate_schema(self.root, "run_summary_schema", run_summary)
        write_json(summary_path, run_summary)
        self._write_incident_summary(run_summary)
        return run_summary
