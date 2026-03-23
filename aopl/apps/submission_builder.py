from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

from aopl.core.io_utils import ensure_dir, now_utc_iso, sha256_file, write_json, write_text
from aopl.core.types import PaperManifest, SubmissionManifest


class SubmissionBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.release_dir = ensure_dir(root / "data" / "paper_assets" / "releases")

    def _collect_files(self, manifest: PaperManifest) -> list[Path]:
        files = [
            self.root / manifest.ko_tex,
            self.root / manifest.en_tex,
            self.root / manifest.bib_file,
            self.root / manifest.appendix_file,
            self.root / manifest.pdf_file,
            self.root / "papers" / "builds" / f"{manifest.problem_id}_paper_manifest.json",
        ]
        return [file for file in files if file.exists()]

    def build(self, manifest: PaperManifest) -> SubmissionManifest:
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

        notes = (
            f"# 릴리즈 노트\n\n"
            f"- 문제 식별자: {manifest.problem_id}\n"
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
        )
        write_json(self.release_dir / f"{base_name}_submission_manifest.json", submission.to_dict())
        return submission
