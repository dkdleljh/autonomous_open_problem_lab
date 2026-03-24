from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from aopl.core.io_utils import (
    ensure_dir,
    now_utc_iso,
    read_json,
    resolve_under_root,
    sha256_file,
    write_json,
    write_text,
)
from aopl.core.schema_utils import validate_schema
from aopl.core.types import (
    FormalizationReport,
    PaperManifest,
    SubmissionManifest,
    VerificationReport,
)


class SubmissionBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.release_dir = ensure_dir(root / "data" / "paper_assets" / "releases")

    def _incident_summary(self) -> dict[str, object]:
        payload = read_json(self.root / "data" / "audit_logs" / "last_incident_summary.json", default={})
        return payload if isinstance(payload, dict) else {}

    def _doctor_summary(self) -> dict[str, object]:
        payload = read_json(self.root / "data" / "audit_logs" / "last_doctor_report.json", default={})
        return payload if isinstance(payload, dict) else {}

    def _collect_files(self, manifest: PaperManifest) -> list[Path]:
        files = [
            resolve_under_root(self.root, manifest.ko_tex),
            resolve_under_root(self.root, manifest.en_tex),
            resolve_under_root(self.root, manifest.bib_file),
            resolve_under_root(self.root, manifest.appendix_file),
            resolve_under_root(self.root, manifest.pdf_file),
            resolve_under_root(
                self.root, Path("papers") / "builds" / f"{manifest.problem_id}_paper_manifest.json"
            ),
        ]
        unique_files: list[Path] = []
        seen: set[Path] = set()
        for file in files:
            if file.is_symlink():
                raise ValueError(f"심볼릭 링크는 제출 패키지에 포함할 수 없습니다: {file}")
            if file in seen or not file.exists():
                continue
            seen.add(file)
            unique_files.append(file)
        return unique_files

    def build(
        self,
        manifest: PaperManifest,
        verification: VerificationReport | None = None,
        formal_report: FormalizationReport | None = None,
    ) -> SubmissionManifest:
        stamp = now_utc_iso().replace(":", "-").replace("+00:00", "Z")
        base_name = f"{manifest.problem_id}_{stamp}"
        package_file = self.release_dir / f"{base_name}.zip"
        source_bundle_file = self.release_dir / f"{base_name}_source.tar.gz"
        checksum_file = self.release_dir / f"{base_name}_checksums.txt"
        release_notes_file = self.release_dir / f"{base_name}_release_notes.md"

        files = self._collect_files(manifest)
        if not files:
            raise FileNotFoundError("제출 패키지에 포함할 파일이 없어 빌드를 진행할 수 없습니다.")

        with zipfile.ZipFile(package_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in files:
                archive.write(file, arcname=file.relative_to(self.root))

        with tarfile.open(source_bundle_file, "w:gz") as archive:
            for file in files:
                archive.add(file, arcname=file.relative_to(self.root))

        checksum_lines: list[str] = []
        for file in [package_file, source_bundle_file, *files]:
            checksum_lines.append(f"{sha256_file(file)}  {file.name}")
        write_text(checksum_file, "\n".join(checksum_lines) + "\n")

        verification_summary = {
            "passed": verification.passed if verification is not None else None,
            "gate_reason": verification.gate_reason if verification is not None else "unknown",
            "critical_issue_count": len(verification.critical_issues)
            if verification is not None
            else 0,
            "warning_count": len(verification.warnings) if verification is not None else 0,
            "critical_issue_preview": (
                verification.critical_issues[:2] if verification is not None else []
            ),
            "warning_preview": verification.warnings[:2] if verification is not None else [],
        }
        doctor_summary = self._doctor_summary()
        failed_policy_checks = [
            item.get("name")
            for item in doctor_summary.get("checks", [])
            if isinstance(item, dict)
            and item.get("category") == "policy"
            and item.get("passed") is False
            and isinstance(item.get("name"), str)
        ]
        notes = (
            f"# 릴리즈 노트\n\n"
            f"- 문제 식별자: {manifest.problem_id}\n"
            f"- 논문화 backend: {manifest.backend}\n"
            f"- PDF 아티팩트 유형: {manifest.pdf_artifact_kind}\n"
            f"- PDF 빌드 성공: {manifest.pdf_build_success}\n"
            f"- 검증 통과: {verification_summary['passed']}\n"
            f"- 검증 게이트 사유: {verification_summary['gate_reason']}\n"
            f"- 검증 중대 이슈 수: {verification_summary['critical_issue_count']}\n"
            f"- 검증 경고 수: {verification_summary['warning_count']}\n"
            f"- 검증 중대 이슈 미리보기: {', '.join(verification_summary['critical_issue_preview']) if verification_summary['critical_issue_preview'] else 'none'}\n"
            f"- 검증 경고 미리보기: {', '.join(verification_summary['warning_preview']) if verification_summary['warning_preview'] else 'none'}\n"
            f"- 형식화 backend: {formal_report.backend if formal_report is not None else 'unknown'}\n"
            f"- 형식화 아티팩트 유형: {formal_report.artifact_kind if formal_report is not None else 'unknown'}\n"
            f"- 미해결 obligation 수: {len(formal_report.obligations_unresolved) if formal_report is not None else 'unknown'}\n"
            f"- 최근 blocked 수: {self._incident_summary().get('blocked_count', 0)}\n"
            f"- 최근 failure class 요약: {self._incident_summary().get('failure_class_summary', {})}\n"
            f"- transient lookback days: {self._incident_summary().get('policy_context', {}).get('transient_failure_lookback_days', 'unknown')}\n"
            f"- default transient escalation threshold: {self._incident_summary().get('policy_context', {}).get('default_transient_failure_escalation_threshold', 'unknown')}\n"
            f"- stage transient thresholds: {self._incident_summary().get('policy_context', {}).get('stage_transient_failure_thresholds', {})}\n"
            f"- doctor strict 통과: {doctor_summary.get('strict_passed', 'unknown')}\n"
            f"- doctor 정책 lint 실패 수: {doctor_summary.get('policy_lint_summary', {}).get('failed_policy_checks', 'unknown')}\n"
            f"- doctor 정책 lint 실패 항목: {failed_policy_checks if failed_policy_checks else 'none'}\n"
            f"- 생성 시각: {stamp}\n"
            f"- 포함 파일 수: {len(files)}\n"
            f"- 자동 품질 게이트 통과 후 생성됨\n"
        )
        write_text(release_notes_file, notes)

        submission = SubmissionManifest(
            problem_id=manifest.problem_id,
            package_file=str(package_file.relative_to(self.root)),
            source_bundle_file=str(source_bundle_file.relative_to(self.root)),
            checksum_file=str(checksum_file.relative_to(self.root)),
            release_notes_file=str(release_notes_file.relative_to(self.root)),
            included_files=[str(file.relative_to(self.root)) for file in files],
            backend_summary={
                "paper_generator": manifest.backend,
                "formalizer": formal_report.backend if formal_report is not None else "unknown",
                **(verification.backend_summary if verification is not None else {}),
            },
            artifact_summary={
                "pdf_artifact_kind": manifest.pdf_artifact_kind,
                "pdf_build_attempted": manifest.pdf_build_attempted,
                "pdf_build_success": manifest.pdf_build_success,
                "formalization_artifact_kind": (
                    formal_report.artifact_kind if formal_report is not None else "unknown"
                ),
                "formal_build_success": (
                    formal_report.build_success if formal_report is not None else None
                ),
            },
            verification_summary=verification_summary,
            incident_summary=self._incident_summary(),
            doctor_summary=doctor_summary,
        )
        validate_schema(self.root, "submission_manifest_schema", submission.to_dict())
        write_json(self.release_dir / f"{base_name}_submission_manifest.json", submission.to_dict())
        return submission
