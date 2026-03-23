from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aopl.apps.counterexample_engine import CounterexampleEngine
from aopl.apps.formalizer import Formalizer
from aopl.apps.harvester import Harvester
from aopl.apps.normalizer import Normalizer
from aopl.apps.orchestrator import Orchestrator
from aopl.apps.paper_generator import PaperGenerator
from aopl.apps.proof_engine import ProofEngine
from aopl.apps.registry import Registry
from aopl.apps.scorer import Scorer
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.apps.verifier import Verifier
from aopl.core.io_utils import read_json
from aopl.core.paths import detect_project_root, locate_workspace_root
from aopl.core.types import (
    CounterexampleReport,
    FormalizationReport,
    NormalizedProblem,
    PipelineStage,
    ProblemRecord,
    ProofDAG,
    ProofNode,
    VerificationReport,
)


def _root_from_args(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root).resolve()
    cwd_root = locate_workspace_root(Path.cwd())
    if (cwd_root / "pyproject.toml").exists() and (cwd_root / "aopl").exists():
        return cwd_root
    return detect_project_root()


def _load_problem_records(root: Path) -> list[ProblemRecord]:
    payload = read_json(root / "data" / "registry" / "problem_registry.json", default=[])
    records: list[ProblemRecord] = []
    if not isinstance(payload, list):
        return records
    for item in payload:
        status_raw = item.get("status", PipelineStage.REGISTERED.value)
        status = (
            PipelineStage(status_raw)
            if status_raw in PipelineStage._value2member_map_
            else PipelineStage.REGISTERED
        )
        records.append(
            ProblemRecord(
                problem_id=item.get("problem_id", ""),
                title=item.get("title", ""),
                domain=item.get("domain", ""),
                statement=item.get("statement", ""),
                assumptions=list(item.get("assumptions", [])),
                goal=item.get("goal", ""),
                aliases=list(item.get("aliases", [])),
                sources=list(item.get("sources", [])),
                status=status,
                metadata=dict(item.get("metadata", {})),
            )
        )
    return records


def _load_normalized(root: Path, problem_id: str) -> NormalizedProblem:
    payload = read_json(
        root / "data" / "normalized" / f"{problem_id}_normalized.json", default=None
    )
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"정규화 파일을 찾을 수 없습니다: {problem_id}")
    return NormalizedProblem(
        problem_id=payload["problem_id"],
        title=payload["title"],
        domain=payload["domain"],
        objects=list(payload["objects"]),
        assumptions=list(payload["assumptions"]),
        target=payload["target"],
        equivalent_forms=list(payload["equivalent_forms"]),
        weak_forms=list(payload["weak_forms"]),
        strong_forms=list(payload["strong_forms"]),
        notation_map=dict(payload["notation_map"]),
        source_problem=dict(payload["source_problem"]),
    )


def _load_dag(root: Path, problem_id: str) -> ProofDAG:
    payload = read_json(root / "data" / "proof_dag" / f"{problem_id}_proof_dag.json", default=None)
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"proof DAG 파일을 찾을 수 없습니다: {problem_id}")
    nodes = [
        ProofNode(
            node_id=node["node_id"],
            node_type=node["node_type"],
            title=node["title"],
            statement=node["statement"],
            dependencies=list(node["dependencies"]),
            status=node["status"],
        )
        for node in payload.get("nodes", [])
    ]
    return ProofDAG(
        problem_id=payload["problem_id"],
        root_node=payload["root_node"],
        target_node=payload["target_node"],
        nodes=nodes,
        edges=list(payload.get("edges", [])),
    )


def _load_counterexample(root: Path, problem_id: str) -> CounterexampleReport:
    payload = read_json(
        root / "data" / "experiments" / f"{problem_id}_counterexample.json", default=None
    )
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"반례 탐색 파일을 찾을 수 없습니다: {problem_id}")
    return CounterexampleReport(
        problem_id=payload["problem_id"],
        checked_variant=payload["checked_variant"],
        found_counterexample=bool(payload["found_counterexample"]),
        counterexample=payload.get("counterexample"),
        explored_bound=int(payload["explored_bound"]),
        seed=int(payload["seed"]),
        elapsed_seconds=float(payload["elapsed_seconds"]),
        weak_variant_recommendation=payload.get("weak_variant_recommendation"),
    )


def _load_verification(root: Path, problem_id: str) -> VerificationReport:
    payload = read_json(
        root / "data" / "theorem_store" / f"{problem_id}_verification.json", default=None
    )
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"검증 파일을 찾을 수 없습니다: {problem_id}")
    return VerificationReport(
        problem_id=payload["problem_id"],
        passed=bool(payload["passed"]),
        critical_issues=list(payload["critical_issues"]),
        warnings=list(payload["warnings"]),
        counterexample_report=dict(payload["counterexample_report"]),
        gate_reason=payload["gate_reason"],
    )


def _load_formal_report(root: Path, problem_id: str) -> FormalizationReport:
    payload = read_json(
        root / "formal" / "proof_obligations" / f"{problem_id}_formalization_report.json",
        default=None,
    )
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"형식화 보고서를 찾을 수 없습니다: {problem_id}")
    return FormalizationReport(
        problem_id=payload["problem_id"],
        lean_file=payload["lean_file"],
        imports=list(payload["imports"]),
        obligations_total=int(payload["obligations_total"]),
        obligations_resolved=int(payload["obligations_resolved"]),
        obligations_unresolved=list(payload["obligations_unresolved"]),
        build_attempted=bool(payload["build_attempted"]),
        build_success=bool(payload["build_success"]),
        build_log_file=payload["build_log_file"],
    )


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _command_init(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    root.mkdir(parents=True, exist_ok=True)
    print(f"프로젝트 루트 준비 완료: {root}")


def _command_harvest(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    harvested = Harvester(root).harvest()
    records = Registry(root).register(harvested)
    _print_json({"harvested": len(harvested), "registered": len(records)})


def _command_normalize(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    normalizer = Normalizer(root)
    records = _load_problem_records(root)
    outputs = [normalizer.normalize(record).to_dict() for record in records]
    _print_json(
        {"normalized": len(outputs), "problem_ids": [item["problem_id"] for item in outputs]}
    )


def _command_score(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    scorer = Scorer(root)
    records = _load_problem_records(root)
    scores = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        scores.append(scorer.score(normalized).to_dict())
    _print_json({"scored": len(scores), "scores": scores})


def _command_counterexample(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    engine = CounterexampleEngine(root)
    records = _load_problem_records(root)
    reports = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        reports.append(engine.run(normalized).to_dict())
    _print_json({"counterexample_checked": len(reports), "reports": reports})


def _command_proof(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    engine = ProofEngine(root)
    records = _load_problem_records(root)
    dags = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        dags.append(engine.build(normalized).to_dict())
    _print_json({"proof_dag_built": len(dags)})


def _command_verify(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    verifier = Verifier(root)
    records = _load_problem_records(root)
    reports = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        dag = _load_dag(root, record.problem_id)
        counterexample_report = _load_counterexample(root, record.problem_id)
        reports.append(verifier.verify(normalized, dag, counterexample_report).to_dict())
    _print_json({"verified": len(reports), "reports": reports})


def _command_formalize(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    formalizer = Formalizer(root)
    records = _load_problem_records(root)
    reports = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        dag = _load_dag(root, record.problem_id)
        reports.append(formalizer.generate(normalized, dag).to_dict())
    _print_json({"formalized": len(reports), "reports": reports})


def _command_paper(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    generator = PaperGenerator(root)
    records = _load_problem_records(root)
    manifests = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        dag = _load_dag(root, record.problem_id)
        verification = _load_verification(root, record.problem_id)
        formal_report = _load_formal_report(root, record.problem_id)
        manifest = generator.generate(normalized, dag, verification, formal_report)
        qa_passed, qa_reason = generator.qa_check(manifest)
        manifests.append(
            {"manifest": manifest.to_dict(), "qa_passed": qa_passed, "qa_reason": qa_reason}
        )
    _print_json({"papers": manifests})


def _command_submission(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    builder = SubmissionBuilder(root)
    records = _load_problem_records(root)
    manifests = []
    for record in records:
        payload = read_json(
            root / "papers" / "builds" / f"{record.problem_id}_paper_manifest.json", default=None
        )
        if not isinstance(payload, dict):
            raise FileNotFoundError(f"논문 매니페스트를 찾을 수 없습니다: {record.problem_id}")
        from aopl.core.types import PaperManifest

        paper_manifest = PaperManifest(
            problem_id=payload["problem_id"],
            theorem_numbers=list(payload["theorem_numbers"]),
            equation_numbers=list(payload["equation_numbers"]),
            reference_keys=list(payload["reference_keys"]),
            ko_tex=payload["ko_tex"],
            en_tex=payload["en_tex"],
            bib_file=payload["bib_file"],
            appendix_file=payload["appendix_file"],
            pdf_file=payload["pdf_file"],
        )
        manifests.append(builder.build(paper_manifest).to_dict())
    _print_json({"submission_packages": manifests})


def _command_run_all(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    summary = Orchestrator(root).run(limit=args.limit)
    _print_json(summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aopl", description="Autonomous Open Problem Lab CLI")
    parser.add_argument("--root", type=str, default=None, help="프로젝트 루트 경로")
    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init", help="프로젝트 루트를 준비한다")
    init_cmd.set_defaults(func=_command_init)

    harvest_cmd = sub.add_parser("harvest", help="문제 수집과 등록을 실행한다")
    harvest_cmd.set_defaults(func=_command_harvest)

    normalize_cmd = sub.add_parser("normalize", help="정규화를 실행한다")
    normalize_cmd.set_defaults(func=_command_normalize)

    score_cmd = sub.add_parser("score", help="점수 계산을 실행한다")
    score_cmd.set_defaults(func=_command_score)

    counterexample_cmd = sub.add_parser("counterexample", help="반례 탐색을 실행한다")
    counterexample_cmd.set_defaults(func=_command_counterexample)

    proof_cmd = sub.add_parser("proof", help="proof DAG를 생성한다")
    proof_cmd.set_defaults(func=_command_proof)

    verify_cmd = sub.add_parser("verify", help="검증 엔진을 실행한다")
    verify_cmd.set_defaults(func=_command_verify)

    formalize_cmd = sub.add_parser("formalize", help="형식화 스켈레톤을 생성한다")
    formalize_cmd.set_defaults(func=_command_formalize)

    paper_cmd = sub.add_parser("paper", help="논문 초안을 생성한다")
    paper_cmd.set_defaults(func=_command_paper)

    submission_cmd = sub.add_parser("submission", help="제출 패키지를 생성한다")
    submission_cmd.set_defaults(func=_command_submission)

    run_all_cmd = sub.add_parser("run-all", help="전체 파이프라인을 실행한다")
    run_all_cmd.add_argument("--limit", type=int, default=None, help="처리할 문제 수 제한")
    run_all_cmd.set_defaults(func=_command_run_all)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
