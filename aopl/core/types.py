from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class PipelineStage(StrEnum):
    REGISTERED = "REGISTERED"
    HARVESTED = "HARVESTED"
    NORMALIZED = "NORMALIZED"
    SCORED = "SCORED"
    SELECTED = "SELECTED"
    COUNTEREXAMPLE_CHECKED = "COUNTEREXAMPLE_CHECKED"
    LEMMA_GRAPH_BUILT = "LEMMA_GRAPH_BUILT"
    DRAFT_PROOF_CREATED = "DRAFT_PROOF_CREATED"
    INTERNAL_VERIFICATION_PASSED = "INTERNAL_VERIFICATION_PASSED"
    FORMALIZATION_ATTEMPTED = "FORMALIZATION_ATTEMPTED"
    PAPER_DRAFT_GENERATED = "PAPER_DRAFT_GENERATED"
    PAPER_QA_PASSED = "PAPER_QA_PASSED"
    SUBMISSION_PACKAGE_READY = "SUBMISSION_PACKAGE_READY"
    RELEASED = "RELEASED"
    BLOCKED = "BLOCKED"


@dataclass
class StageEvent:
    problem_id: str
    stage: PipelineStage
    gate_name: str
    passed: bool
    reason: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProblemRecord:
    problem_id: str
    title: str
    domain: str
    statement: str
    assumptions: list[str]
    goal: str
    aliases: list[str]
    sources: list[dict[str, Any]]
    status: PipelineStage = PipelineStage.REGISTERED
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class NormalizedProblem:
    problem_id: str
    title: str
    domain: str
    objects: list[str]
    assumptions: list[str]
    target: str
    equivalent_forms: list[str]
    weak_forms: list[str]
    strong_forms: list[str]
    notation_map: dict[str, str]
    source_problem: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreCard:
    problem_id: str
    formalizability: float
    decomposability: float
    library_fit: float
    counterexample_searchability: float
    paperability: float
    score: float
    selected: bool
    rationale: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CounterexampleReport:
    problem_id: str
    backend: str
    checked_variant: str
    found_counterexample: bool
    counterexample: dict[str, Any] | None
    explored_bound: int
    seed: int
    elapsed_seconds: float
    weak_variant_recommendation: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProofNode:
    node_id: str
    node_type: str
    title: str
    statement: str
    dependencies: list[str]
    status: str


@dataclass
class ProofDAG:
    problem_id: str
    backend: str
    root_node: str
    target_node: str
    nodes: list[ProofNode]
    edges: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "backend": self.backend,
            "root_node": self.root_node,
            "target_node": self.target_node,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": self.edges,
        }


@dataclass
class VerificationReport:
    problem_id: str
    backend_summary: dict[str, str]
    passed: bool
    critical_issues: list[str]
    warnings: list[str]
    counterexample_report: dict[str, Any]
    gate_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FormalizationReport:
    problem_id: str
    backend: str
    lean_file: str
    imports: list[str]
    obligations_total: int
    obligations_resolved: int
    obligations_unresolved: list[str]
    build_attempted: bool
    build_success: bool
    build_log_file: str
    artifact_kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PaperManifest:
    problem_id: str
    backend: str
    theorem_numbers: list[str]
    equation_numbers: list[str]
    reference_keys: list[str]
    ko_tex: str
    en_tex: str
    bib_file: str
    appendix_file: str
    pdf_file: str
    pdf_build_attempted: bool
    pdf_build_success: bool
    pdf_artifact_kind: str
    incident_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubmissionManifest:
    problem_id: str
    package_file: str
    source_bundle_file: str
    checksum_file: str
    release_notes_file: str
    included_files: list[str]
    backend_summary: dict[str, str]
    artifact_summary: dict[str, Any]
    verification_summary: dict[str, Any]
    incident_summary: dict[str, Any] = field(default_factory=dict)
    doctor_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BANNED_PROOF_PHRASES = ["자명하다", "생략한다", "유사하게", "당연하다"]
