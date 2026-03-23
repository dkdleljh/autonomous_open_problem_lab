from __future__ import annotations

from dataclasses import dataclass

from aopl.core.types import PipelineStage

PIPELINE_ORDER: list[PipelineStage] = [
    PipelineStage.REGISTERED,
    PipelineStage.HARVESTED,
    PipelineStage.NORMALIZED,
    PipelineStage.SCORED,
    PipelineStage.SELECTED,
    PipelineStage.COUNTEREXAMPLE_CHECKED,
    PipelineStage.LEMMA_GRAPH_BUILT,
    PipelineStage.DRAFT_PROOF_CREATED,
    PipelineStage.INTERNAL_VERIFICATION_PASSED,
    PipelineStage.FORMALIZATION_ATTEMPTED,
    PipelineStage.PAPER_DRAFT_GENERATED,
    PipelineStage.PAPER_QA_PASSED,
    PipelineStage.SUBMISSION_PACKAGE_READY,
    PipelineStage.RELEASED,
]


@dataclass
class TransitionResult:
    current: PipelineStage
    next_stage: PipelineStage
    blocked: bool
    reason: str


class StageMachine:
    def __init__(self) -> None:
        self.order = PIPELINE_ORDER

    def next_stage(self, current: PipelineStage) -> PipelineStage:
        if current == PipelineStage.BLOCKED:
            return PipelineStage.BLOCKED
        current_index = self.order.index(current)
        if current_index + 1 >= len(self.order):
            return current
        return self.order[current_index + 1]

    def transition(
        self,
        current: PipelineStage,
        gate_passed: bool,
        gate_reason: str,
    ) -> TransitionResult:
        if not gate_passed:
            return TransitionResult(
                current=current,
                next_stage=PipelineStage.BLOCKED,
                blocked=True,
                reason=gate_reason,
            )
        return TransitionResult(
            current=current,
            next_stage=self.next_stage(current),
            blocked=False,
            reason=gate_reason,
        )
