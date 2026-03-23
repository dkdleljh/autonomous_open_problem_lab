from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from aopl.apps.harvester import Harvester
from aopl.apps.normalizer import Normalizer
from aopl.apps.orchestrator import Orchestrator
from aopl.apps.registry import Registry
from aopl.apps.scorer import Scorer
from aopl.apps.submission_builder import SubmissionBuilder
from aopl.apps.verifier import Verifier
from aopl.core.config_store import ConfigStore
from aopl.core.io_utils import read_json
from aopl.core.paths import detect_project_root, locate_workspace_root
from aopl.core.schema_utils import validate_schema
from aopl.core.types import (
    CounterexampleReport,
    FormalizationReport,
    NormalizedProblem,
    PaperManifest,
    PipelineStage,
    ProblemRecord,
    ProofDAG,
    ProofNode,
    VerificationReport,
)
from aopl.services.engine_factory import EngineFactory


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
    validate_schema(root, "problem_registry_schema", payload)
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
    validate_schema(root, "normalized_problem_schema", payload)
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
    validate_schema(root, "proof_dag_schema", payload)
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
        backend=payload.get("backend", "unknown"),
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
    validate_schema(root, "counterexample_report_schema", payload)
    return CounterexampleReport(
        problem_id=payload["problem_id"],
        backend=payload.get("backend", "unknown"),
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
    validate_schema(root, "verification_report_schema", payload)
    return VerificationReport(
        problem_id=payload["problem_id"],
        backend_summary=dict(payload.get("backend_summary", {})),
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
    validate_schema(root, "formalization_report_schema", payload)
    return FormalizationReport(
        problem_id=payload["problem_id"],
        backend=payload.get("backend", "unknown"),
        lean_file=payload["lean_file"],
        imports=list(payload["imports"]),
        obligations_total=int(payload["obligations_total"]),
        obligations_resolved=int(payload["obligations_resolved"]),
        obligations_unresolved=list(payload["obligations_unresolved"]),
        build_attempted=bool(payload["build_attempted"]),
        build_success=bool(payload["build_success"]),
        build_log_file=payload["build_log_file"],
        artifact_kind=payload.get("artifact_kind", "unknown"),
    )


def _load_paper_manifest(root: Path, problem_id: str) -> PaperManifest:
    payload = read_json(
        root / "papers" / "builds" / f"{problem_id}_paper_manifest.json", default=None
    )
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"논문 매니페스트를 찾을 수 없습니다: {problem_id}")
    validate_schema(root, "paper_manifest_schema", payload)
    return PaperManifest(
        problem_id=payload["problem_id"],
        backend=payload.get("backend", "unknown"),
        theorem_numbers=list(payload["theorem_numbers"]),
        equation_numbers=list(payload["equation_numbers"]),
        reference_keys=list(payload["reference_keys"]),
        ko_tex=payload["ko_tex"],
        en_tex=payload["en_tex"],
        bib_file=payload["bib_file"],
        appendix_file=payload["appendix_file"],
        pdf_file=payload["pdf_file"],
        pdf_build_attempted=bool(payload.get("pdf_build_attempted", False)),
        pdf_build_success=bool(payload.get("pdf_build_success", False)),
        pdf_artifact_kind=payload.get("pdf_artifact_kind", "unknown"),
    )


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _record_provenance_summary(record: ProblemRecord) -> dict[str, Any]:
    provenance = record.metadata.get("provenance", {}) if isinstance(record.metadata, dict) else {}
    if not isinstance(provenance, dict):
        provenance = {}
    return {
        "harvest_batch_id": provenance.get("harvest_batch_id"),
        "harvested_at": provenance.get("harvested_at"),
        "source_signature": provenance.get("source_signature"),
        "candidate_hash": provenance.get("candidate_hash"),
    }


def _verification_summary(report: VerificationReport) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "gate_reason": report.gate_reason,
        "critical_issue_count": len(report.critical_issues),
        "warning_count": len(report.warnings),
        "backend_summary": dict(report.backend_summary),
    }


def _run_optional(command: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _command_doctor(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    quality_policy = ConfigStore(root).quality_policy().get("doctor", {})
    profiles = quality_policy.get("profiles", {}) if isinstance(quality_policy, dict) else {}
    configured_default_profile = (
        quality_policy.get("default_profile", "local") if isinstance(quality_policy, dict) else "local"
    )
    active_profile = args.profile or configured_default_profile
    profile_policy = profiles.get(active_profile, {})
    threshold = (
        float(args.min_score)
        if args.min_score is not None
        else float(profile_policy.get("min_score", 100))
    )
    required_check_names = list(profile_policy.get("required_checks", []))
    checks: list[dict[str, Any]] = []

    def add_check(
        name: str,
        passed: bool,
        detail: str,
        category: str,
        weight: int = 1,
        profiles: list[str] | None = None,
    ) -> None:
        checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": detail,
                "category": category,
                "weight": weight,
                "profiles": list(profiles or ["local", "ci", "github_release"]),
            }
        )

    add_check("프로젝트 루트", root.exists(), str(root), "workspace")
    add_check("git 저장소", (root / ".git").exists(), ".git 존재 여부", "git")

    code_remote, out_remote, _ = _run_optional(["git", "remote", "get-url", "origin"], root)
    add_check(
        "원격 origin",
        code_remote == 0 and bool(out_remote),
        out_remote if out_remote else "origin 미설정",
        "git",
    )

    code_branch, out_branch, _ = _run_optional(["git", "branch", "--show-current"], root)
    github_ref_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    github_ref_type = os.environ.get("GITHUB_REF_TYPE", "").strip()
    branch_passed = code_branch == 0 and (
        out_branch == "main" or github_ref_name == "main" or github_ref_type == "tag"
    )
    add_check(
        "현재 브랜치",
        branch_passed,
        out_branch or github_ref_name or github_ref_type or "브랜치 확인 실패",
        "git",
    )

    code_status, out_status, _ = _run_optional(["git", "status", "--short"], root)
    clean = code_status == 0 and not out_status.strip()
    add_check(
        "워킹트리 청결",
        clean,
        "clean" if clean else "미커밋 변경 존재",
        "git",
    )

    add_check(
        "pytest 사용 가능",
        shutil.which("pytest") is not None or (root / ".venv" / "bin" / "pytest").exists(),
        "pytest 실행 파일 확인",
        "tooling",
    )
    add_check("Lean", shutil.which("lean") is not None, "lean 실행 파일 확인", "tooling")
    add_check("Lake", shutil.which("lake") is not None, "lake 실행 파일 확인", "tooling")
    add_check(
        "LaTeX",
        shutil.which("latexmk") is not None or shutil.which("pdflatex") is not None,
        "latexmk/pdflatex 확인",
        "tooling",
        profiles=["github_release"],
    )
    add_check(
        "GitHub CLI",
        shutil.which("gh") is not None,
        "gh 실행 파일 확인",
        "tooling",
        profiles=["github_release"],
    )

    github_token = bool(os.environ.get("GITHUB_TOKEN"))
    github_repo = bool(os.environ.get("GITHUB_REPOSITORY"))
    add_check(
        "GITHUB_TOKEN",
        github_token,
        "환경변수 설정 여부",
        "release",
        weight=2,
        profiles=["github_release"],
    )
    add_check(
        "GITHUB_REPOSITORY",
        github_repo,
        "환경변수 설정 여부",
        "release",
        weight=2,
        profiles=["github_release"],
    )

    docs_required = [
        root / "README.md",
        root / "PROGRAM_USER_GUIDE.md",
        root / "PROGRAM_DETAILED_DESIGN.md",
        root / "PROGRAM_REALITY_CHECK_KO.md",
        root / "PROGRAM_100_SCORE_ROADMAP_KO.md",
    ]
    missing_docs = [path.name for path in docs_required if not path.exists()]
    add_check(
        "핵심 한글 문서",
        not missing_docs,
        "누락 없음" if not missing_docs else f"누락: {', '.join(missing_docs)}",
        "docs",
        weight=2,
    )

    workflow_files = [root / ".github" / "workflows" / "ci.yml", root / ".github" / "workflows" / "release.yml"]
    missing_workflows = [path.name for path in workflow_files if not path.exists()]
    add_check(
        "GitHub 워크플로우",
        not missing_workflows,
        "누락 없음" if not missing_workflows else f"누락: {', '.join(missing_workflows)}",
        "release",
    )

    total_weight = sum(item["weight"] for item in checks)
    earned_weight = sum(item["weight"] for item in checks if item["passed"])
    overall_score = round((earned_weight / total_weight) * 100, 1) if total_weight else 0.0

    profile_checks = [
        item
        for item in checks
        if active_profile in item.get("profiles", ["local", "ci", "github_release"])
    ]
    profile_total_weight = sum(item["weight"] for item in profile_checks)
    profile_earned_weight = sum(item["weight"] for item in profile_checks if item["passed"])
    profile_score = (
        round((profile_earned_weight / profile_total_weight) * 100, 1)
        if profile_total_weight
        else 0.0
    )
    check_lookup = {item["name"]: item for item in checks}
    blocking_checks = [
        {
            "name": name,
            "detail": check_lookup[name]["detail"] if name in check_lookup else "정의되지 않은 체크",
        }
        for name in required_check_names
        if name not in check_lookup or not check_lookup[name]["passed"]
    ]
    strict_passed = profile_score >= threshold and not blocking_checks

    by_category: dict[str, dict[str, Any]] = {}
    for item in checks:
        category = item["category"]
        entry = by_category.setdefault(category, {"passed": 0, "total": 0})
        entry["total"] += 1
        entry["passed"] += 1 if item["passed"] else 0

    payload = {
        "doctor_score": overall_score,
        "active_profile_score": profile_score,
        "active_profile": active_profile,
        "strict_passed": strict_passed,
        "policy": {
            "default_profile": configured_default_profile,
            "required_checks": required_check_names,
            "min_score": threshold,
        },
        "summary": {
            "total_checks": len(checks),
            "passed_checks": sum(1 for item in checks if item["passed"]),
            "failed_checks": sum(1 for item in checks if not item["passed"]),
            "profile_checks": len(profile_checks),
            "profile_failed_checks": sum(1 for item in profile_checks if not item["passed"]),
        },
        "category_summary": by_category,
        "blocking_checks": blocking_checks,
        "checks": checks,
        "interpretation": {
            "100점 의미": "활성 프로필에서 요구하는 핵심 운영 조건을 전부 충족한 상태",
            "주의": "이 점수는 운영 준비도 점수이며, 모든 수학 난제 해결 능력 점수가 아니다",
        },
    }
    _print_json(payload)
    if args.strict and not strict_passed:
        raise SystemExit(1)


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
    engine = EngineFactory(root).counterexample_engine()
    records = _load_problem_records(root)
    reports = []
    for record in records:
        normalized = _load_normalized(root, record.problem_id)
        reports.append(engine.run(normalized).to_dict())
    _print_json({"counterexample_checked": len(reports), "reports": reports})


def _command_proof(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    engine = EngineFactory(root).proof_engine()
    records = _load_problem_records(root)
    dags = []
    skipped = []
    for record in records:
        try:
            normalized = _load_normalized(root, record.problem_id)
        except FileNotFoundError as error:
            skipped.append({"problem_id": record.problem_id, "reason": str(error)})
            continue
        counterexample_report = None
        try:
            counterexample_report = _load_counterexample(root, record.problem_id)
        except FileNotFoundError:
            counterexample_report = None
        dag = engine.build(normalized, counterexample_report)
        dags.append(
            {
                "problem_id": record.problem_id,
                "backend": dag.backend,
                "node_count": len(dag.nodes),
                "edge_count": len(dag.edges),
                "provenance_summary": _record_provenance_summary(record),
                "dag": dag.to_dict(),
            }
        )
    _print_json({"proof_dag_built": len(dags), "proofs": dags, "skipped": skipped})


def _command_verify(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    verifier = Verifier(root)
    records = _load_problem_records(root)
    reports = []
    skipped = []
    for record in records:
        try:
            normalized = _load_normalized(root, record.problem_id)
            dag = _load_dag(root, record.problem_id)
            counterexample_report = _load_counterexample(root, record.problem_id)
        except FileNotFoundError as error:
            skipped.append({"problem_id": record.problem_id, "reason": str(error)})
            continue
        report = verifier.verify(normalized, dag, counterexample_report)
        reports.append(
            {
                "problem_id": record.problem_id,
                "provenance_summary": _record_provenance_summary(record),
                "summary": _verification_summary(report),
                "report": report.to_dict(),
            }
        )
    _print_json({"verified": len(reports), "reports": reports, "skipped": skipped})


def _command_formalize(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    formalizer = EngineFactory(root).formalizer()
    records = _load_problem_records(root)
    reports = []
    skipped = []
    for record in records:
        try:
            normalized = _load_normalized(root, record.problem_id)
            dag = _load_dag(root, record.problem_id)
        except FileNotFoundError as error:
            skipped.append({"problem_id": record.problem_id, "reason": str(error)})
            continue
        reports.append(formalizer.generate(normalized, dag).to_dict())
    _print_json({"formalized": len(reports), "reports": reports, "skipped": skipped})


def _command_paper(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    generator = EngineFactory(root).paper_generator()
    records = _load_problem_records(root)
    manifests = []
    skipped = []
    for record in records:
        try:
            normalized = _load_normalized(root, record.problem_id)
            dag = _load_dag(root, record.problem_id)
            verification = _load_verification(root, record.problem_id)
            formal_report = _load_formal_report(root, record.problem_id)
        except FileNotFoundError as error:
            skipped.append({"problem_id": record.problem_id, "reason": str(error)})
            continue
        manifest = generator.generate(normalized, dag, verification, formal_report)
        qa_passed, qa_reason = generator.qa_check(manifest)
        manifests.append(
            {
                "problem_id": record.problem_id,
                "provenance_summary": _record_provenance_summary(record),
                "verification_summary": _verification_summary(verification),
                "manifest": manifest.to_dict(),
                "qa_passed": qa_passed,
                "qa_reason": qa_reason,
            }
        )
    _print_json({"papers": manifests, "skipped": skipped})


def _command_submission(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    builder = SubmissionBuilder(root)
    records = _load_problem_records(root)
    manifests = []
    skipped = []
    for record in records:
        try:
            paper_manifest = _load_paper_manifest(root, record.problem_id)
        except FileNotFoundError as error:
            skipped.append({"problem_id": record.problem_id, "reason": str(error)})
            continue
        verification = None
        formal_report = None
        try:
            verification = _load_verification(root, record.problem_id)
        except FileNotFoundError:
            verification = None
        try:
            formal_report = _load_formal_report(root, record.problem_id)
        except FileNotFoundError:
            formal_report = None
        submission = builder.build(paper_manifest, verification, formal_report)
        manifests.append(
            {
                "problem_id": record.problem_id,
                "provenance_summary": _record_provenance_summary(record),
                "submission": submission.to_dict(),
            }
        )
    _print_json({"submission_packages": manifests, "skipped": skipped})


def _command_run_all(args: argparse.Namespace) -> None:
    root = _root_from_args(args)
    summary = Orchestrator(root).run(limit=args.limit)
    _print_json(summary)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aopl", description="Autonomous Open Problem Lab CLI")
    parser.add_argument("--root", type=str, default=None, help="프로젝트 루트 경로")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_root_argument(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("--root", type=str, default=None, help="프로젝트 루트 경로")

    init_cmd = sub.add_parser("init", help="프로젝트 루트를 준비한다")
    add_root_argument(init_cmd)
    init_cmd.set_defaults(func=_command_init)

    harvest_cmd = sub.add_parser("harvest", help="문제 수집과 등록을 실행한다")
    add_root_argument(harvest_cmd)
    harvest_cmd.set_defaults(func=_command_harvest)

    normalize_cmd = sub.add_parser("normalize", help="정규화를 실행한다")
    add_root_argument(normalize_cmd)
    normalize_cmd.set_defaults(func=_command_normalize)

    score_cmd = sub.add_parser("score", help="점수 계산을 실행한다")
    add_root_argument(score_cmd)
    score_cmd.set_defaults(func=_command_score)

    counterexample_cmd = sub.add_parser("counterexample", help="반례 탐색을 실행한다")
    add_root_argument(counterexample_cmd)
    counterexample_cmd.set_defaults(func=_command_counterexample)

    proof_cmd = sub.add_parser("proof", help="proof DAG를 생성한다")
    add_root_argument(proof_cmd)
    proof_cmd.set_defaults(func=_command_proof)

    verify_cmd = sub.add_parser("verify", help="검증 엔진을 실행한다")
    add_root_argument(verify_cmd)
    verify_cmd.set_defaults(func=_command_verify)

    formalize_cmd = sub.add_parser("formalize", help="형식화 스켈레톤을 생성한다")
    add_root_argument(formalize_cmd)
    formalize_cmd.set_defaults(func=_command_formalize)

    paper_cmd = sub.add_parser("paper", help="논문 초안을 생성한다")
    add_root_argument(paper_cmd)
    paper_cmd.set_defaults(func=_command_paper)

    submission_cmd = sub.add_parser("submission", help="제출 패키지를 생성한다")
    add_root_argument(submission_cmd)
    submission_cmd.set_defaults(func=_command_submission)

    doctor_cmd = sub.add_parser("doctor", help="운영 및 릴리즈 준비 상태를 점검한다")
    add_root_argument(doctor_cmd)
    doctor_cmd.add_argument(
        "--profile",
        choices=["local", "ci", "github_release"],
        default=None,
        help="적용할 운영 프로필",
    )
    doctor_cmd.add_argument("--strict", action="store_true", help="정책 미달 시 종료 코드 1로 실패")
    doctor_cmd.add_argument("--min-score", type=float, default=None, help="strict 기준 최소 점수")
    doctor_cmd.set_defaults(func=_command_doctor)

    run_all_cmd = sub.add_parser("run-all", help="전체 파이프라인을 실행한다")
    add_root_argument(run_all_cmd)
    run_all_cmd.add_argument("--limit", type=int, default=None, help="처리할 문제 수 제한")
    run_all_cmd.set_defaults(func=_command_run_all)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
