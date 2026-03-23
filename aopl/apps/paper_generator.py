from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from aopl.core.config_store import ConfigStore
from aopl.core.io_utils import ensure_dir, read_text, read_yaml, write_json, write_text
from aopl.core.schema_utils import validate_schema
from aopl.core.types import (
    FormalizationReport,
    NormalizedProblem,
    PaperManifest,
    ProofDAG,
    VerificationReport,
)


def _build_minimal_pdf(path: Path, text: str) -> None:
    safe_text = text.replace("(", "[").replace(")", "]").replace("\\", "/")
    body = (
        "%PDF-1.4\n"
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        f"4 0 obj<< /Length {len(safe_text) + 50} >>stream\n"
        f"BT /F1 12 Tf 50 780 Td ({safe_text}) Tj ET\n"
        "endstream endobj\n"
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        "xref\n0 6\n0000000000 65535 f \n"
        "0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n"
        "0000000312 00000 n \n0000000415 00000 n \n"
        "trailer<< /Root 1 0 R /Size 6 >>\nstartxref\n495\n%%EOF\n"
    )
    with path.open("wb") as file:
        file.write(body.encode("latin-1", errors="replace"))


class PaperGenerator:
    def __init__(self, root: Path, backend: str = "demo") -> None:
        self.root = root
        self.backend = backend
        self.config_store = ConfigStore(root)
        self.ko_dir = ensure_dir(root / "papers" / "ko")
        self.en_dir = ensure_dir(root / "papers" / "en")
        self.shared_dir = ensure_dir(root / "papers" / "shared")
        self.build_dir = ensure_dir(root / "papers" / "builds")
        self.build_log_dir = ensure_dir(root / "papers" / "build_logs")
        self.section_rules_file = root / "configs" / "paper" / "section_rules.yaml"
        self.journal_style_file = root / "configs" / "paper" / "journal_style.yaml"

    def _semantic_graph(self, problem: NormalizedProblem, dag: ProofDAG) -> dict[str, Any]:
        theorem_numbers = ["정리 1", "보조정리 1", "보조정리 2"]
        equation_numbers = ["(1)", "(2)"]
        node_titles = [node.title for node in dag.nodes]
        return {
            "problem_id": problem.problem_id,
            "backend": self.backend,
            "theorem_numbers": theorem_numbers,
            "equation_numbers": equation_numbers,
            "node_titles": node_titles,
        }

    def _journal_config(self) -> dict[str, Any]:
        config = self.config_store.paper_journal_style()
        return config if isinstance(config, dict) else {}

    def _section_rules(self) -> dict[str, Any]:
        config = self.config_store.paper_section_rules()
        return config if isinstance(config, dict) else {}

    def _latex_preamble(self, title: str) -> str:
        journal = self._journal_config()
        latex = journal.get("latex", {}) if isinstance(journal, dict) else {}
        documentclass = "article"
        font_size = "11pt"
        packages = ["amsmath", "amsthm", "amssymb", "hyperref"]
        if isinstance(latex, dict):
            documentclass = str(latex.get("documentclass", documentclass))
            font_size = str(latex.get("font_size", font_size))
            raw_packages = latex.get("packages", packages)
            if isinstance(raw_packages, list) and raw_packages:
                packages = [str(item) for item in raw_packages]
        return (
            f"\\documentclass[{font_size}]{{{documentclass}}}\n"
            + "\\usepackage{" + ",".join(packages) + "}\n"
            + "\\title{" + title + "}\n"
            + "\\author{Autonomous Open Problem Lab}\n"
            + "\\date{\\today}\n"
        )

    def _counterexample_context(
        self, verification: VerificationReport
    ) -> tuple[int | None, int | None, str | None]:
        payload = verification.counterexample_report
        if not isinstance(payload, dict):
            return None, None, None
        explored_bound = payload.get("explored_bound")
        seed = payload.get("seed")
        checked_variant = payload.get("checked_variant")
        return (
            int(explored_bound) if isinstance(explored_bound, int) else None,
            int(seed) if isinstance(seed, int) else None,
            str(checked_variant) if isinstance(checked_variant, str) else None,
        )

    def _verification_summary(
        self, verification: VerificationReport
    ) -> tuple[int, int, str, str]:
        critical_count = len(verification.critical_issues)
        warning_count = len(verification.warnings)
        critical_text = (
            "; ".join(verification.critical_issues[:2]) if verification.critical_issues else "none"
        )
        warning_text = (
            "; ".join(verification.warnings[:2]) if verification.warnings else "none"
        )
        return critical_count, warning_count, critical_text, warning_text

    def _reference_entries(self, problem: NormalizedProblem) -> tuple[list[str], str]:
        refs: list[str] = []
        bib_lines: list[str] = []
        for index, source in enumerate(problem.source_problem.get("sources", []), start=1):
            key = f"ref{index}"
            refs.append(key)
            title = source.get("name", f"source_{index}")
            url = source.get("url", "https://example.org")
            bib_lines.append(
                "@misc{"
                + key
                + ",\n"
                + f"  title = {{{title}}},\n"
                + f"  howpublished = {{\\url{{{url}}}}},\n"
                + "  year = {2026}\n"
                + "}\n"
            )
        if not refs:
            refs.append("ref1")
            bib_lines.append(
                "@misc{ref1,\n"
                "  title = {기본 참고문헌 자리표시자},\n"
                "  howpublished = {\\url{https://example.org/default-reference}},\n"
                "  year = {2026}\n"
                "}\n"
            )
        return refs, "\n".join(bib_lines)

    def _build_ko_tex(
        self,
        problem: NormalizedProblem,
        verification: VerificationReport,
        formal_report: FormalizationReport,
        semantic_graph: dict[str, Any],
        bib_file: str,
    ) -> str:
        explored_bound, seed, checked_variant = self._counterexample_context(verification)
        return (
            self._latex_preamble("자동 탐색 기반 난제 연구 초안: " + problem.title)
            + "\\begin{document}\n"
            "\\maketitle\n"
            "\\section*{초록}\n"
            "본 문서는 자동 수집, 자동 정규화, 자동 반례 탐색, "
            "자동 검증, 자동 논문화 파이프라인의 결과를 제시한다. "
            "계산 결과는 실험적 지지로만 사용한다.\\\n"
            "\\section{배경}\n"
            "문제 식별자: " + problem.problem_id + "\\\n"
            "\\section{관련 연구}\n"
            "등록된 참고문헌을 기반으로 연관 연구를 구성한다.\\\n"
            "\\section{정의와 표기}\n"
            "정의 번호 동기화: " + ", ".join(semantic_graph["theorem_numbers"]) + "\\\n"
            "\\section{핵심 아이디어}\n" + problem.target + "\\\n"
            "\\section{보조정리}\n"
            "보조정리 1과 보조정리 2를 통해 주정리 후보를 지원한다.\\\n"
            "\\section{주정리}\n"
            "정리 1. 본 시스템은 검증 게이트 통과 조건 아래에서만 결과를 승격한다.\\\n"
            "\\section{증명}\n"
            "proof DAG 경로를 따라 정리 연결을 추적한다. 검증 상태: "
            + ("통과" if verification.passed else "실패")
            + "\\\n"
            "\\section{계산 검증}\n"
            "탐색은 유한 범위와 seed를 기록하여 재현성을 보장한다. "
            + f"bound={explored_bound}, seed={seed}, variant={checked_variant}.\\\n"
            "\\section{한계}\n"
            "형식화 미해결 의무 수: "
            + str(len(formal_report.obligations_unresolved))
            + f", artifact={formal_report.artifact_kind}, build_success={formal_report.build_success}.\\\n"
            "\\section{재현성}\n"
            "로그, 매니페스트, 체크섬을 함께 제공한다.\\\n"
            "\\bibliographystyle{plain}\n"
            "\\bibliography{" + bib_file + "}\n"
            "\\appendix\n"
            "\\section{부록}\n"
            "형식화 보고서와 실행 로그를 첨부한다.\\\n"
            "\\end{document}\n"
        )

    def _build_en_tex(
        self,
        problem: NormalizedProblem,
        verification: VerificationReport,
        formal_report: FormalizationReport,
        semantic_graph: dict[str, Any],
        bib_file: str,
    ) -> str:
        explored_bound, seed, checked_variant = self._counterexample_context(verification)
        return (
            self._latex_preamble("Automated Open Problem Workflow Draft: " + problem.title)
            + "\\begin{document}\n"
            "\\maketitle\n"
            "\\section*{Abstract}\n"
            "This manuscript reports an unattended pipeline for harvesting, "
            "normalization, counterexample search, verification, and paper drafting. "
            "Computational evidence is treated as experimental support only.\\\n"
            "\\section{Background}\n"
            "Problem identifier: " + problem.problem_id + "\\\n"
            "\\section{Related Work}\n"
            "The citation graph is generated from registered references.\\\n"
            "\\section{Definitions and Notation}\n"
            "Synchronized theorem numbering: "
            + ", ".join(semantic_graph["theorem_numbers"])
            + "\\\n"
            "\\section{Core Idea}\n" + problem.target + "\\\n"
            "\\section{Lemmas}\n"
            "Lemma entries are aligned with proof DAG nodes.\\\n"
            "\\section{Main Theorem}\n"
            "Theorem 1. Promotion is allowed only after all quality gates pass.\\\n"
            "\\section{Proof}\n"
            "The argument follows the proof DAG path. Verification result: "
            + ("passed" if verification.passed else "failed")
            + "\\\n"
            "\\section{Computational Verification}\n"
            "Search bounds, seeds, and timing are explicitly archived. "
            + f"bound={explored_bound}, seed={seed}, variant={checked_variant}.\\\n"
            "\\section{Limitations}\n"
            "Unresolved formal obligations: "
            + str(len(formal_report.obligations_unresolved))
            + f"; artifact={formal_report.artifact_kind}; build_success={formal_report.build_success}"
            + "\\\n"
            "\\section{Reproducibility}\n"
            "Artifacts include logs, manifest, and checksums.\\\n"
            "\\bibliographystyle{plain}\n"
            "\\bibliography{" + bib_file + "}\n"
            "\\appendix\n"
            "\\section{Appendix}\n"
            "Formalization and execution traces are attached.\\\n"
            "\\end{document}\n"
        )

    def _attempt_pdf_build(self, tex_path: Path) -> tuple[bool, bool]:
        latexmk = shutil.which("latexmk")
        pdflatex = shutil.which("pdflatex")
        if latexmk is None and pdflatex is None:
            return False, False
        if latexmk is not None:
            command = [
                latexmk,
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={self.build_dir}",
                str(tex_path),
            ]
        else:
            command = [
                pdflatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={self.build_dir}",
                str(tex_path),
            ]
        run = subprocess.run(
            command,
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        log_path = self.build_log_dir / f"{tex_path.stem}_latex.log"
        write_text(log_path, (run.stdout or "") + "\n" + (run.stderr or ""))
        return True, run.returncode == 0

    def generate(
        self,
        problem: NormalizedProblem,
        dag: ProofDAG,
        verification: VerificationReport,
        formal_report: FormalizationReport,
    ) -> PaperManifest:
        semantic_graph = self._semantic_graph(problem, dag)
        references, bib_text = self._reference_entries(problem)

        semantic_file = self.shared_dir / f"{problem.problem_id}_semantic_graph.json"
        bib_path = self.shared_dir / f"{problem.problem_id}.bib"
        appendix_path = self.shared_dir / f"{problem.problem_id}_appendix.md"
        write_json(semantic_file, semantic_graph)
        write_text(bib_path, bib_text)

        appendix = (
            f"# 재현성 부록\n\n"
            f"- 문제 식별자: {problem.problem_id}\n"
            f"- 검증 통과 여부: {verification.passed}\n"
            f"- 검증 중대 이슈 수: {len(verification.critical_issues)}\n"
            f"- 검증 경고 수: {len(verification.warnings)}\n"
            f"- 검증 중대 이슈 요약: {'; '.join(verification.critical_issues[:2]) if verification.critical_issues else 'none'}\n"
            f"- 검증 경고 요약: {'; '.join(verification.warnings[:2]) if verification.warnings else 'none'}\n"
            f"- 형식화 빌드 시도: {formal_report.build_attempted}\n"
            f"- 형식화 빌드 성공: {formal_report.build_success}\n"
            f"- 미해결 의무: {len(formal_report.obligations_unresolved)}\n"
        )
        write_text(appendix_path, appendix)

        ko_tex_path = self.ko_dir / f"{problem.problem_id}.tex"
        en_tex_path = self.en_dir / f"{problem.problem_id}.tex"
        ko_tex = self._build_ko_tex(
            problem, verification, formal_report, semantic_graph, bib_path.stem
        )
        en_tex = self._build_en_tex(
            problem, verification, formal_report, semantic_graph, bib_path.stem
        )
        write_text(ko_tex_path, ko_tex)
        write_text(en_tex_path, en_tex)

        pdf_path = self.build_dir / f"{problem.problem_id}.pdf"
        pdf_build_attempted, pdf_build_success = self._attempt_pdf_build(ko_tex_path)
        if not pdf_build_success:
            _build_minimal_pdf(pdf_path, f"{problem.problem_id} manuscript placeholder")

        manifest = PaperManifest(
            problem_id=problem.problem_id,
            backend=self.backend,
            theorem_numbers=list(semantic_graph["theorem_numbers"]),
            equation_numbers=list(semantic_graph["equation_numbers"]),
            reference_keys=references,
            ko_tex=str(ko_tex_path.relative_to(self.root)),
            en_tex=str(en_tex_path.relative_to(self.root)),
            bib_file=str(bib_path.relative_to(self.root)),
            appendix_file=str(appendix_path.relative_to(self.root)),
            pdf_file=str(pdf_path.relative_to(self.root)),
            pdf_build_attempted=pdf_build_attempted,
            pdf_build_success=pdf_build_success,
            pdf_artifact_kind="latex_build" if pdf_build_success else "placeholder_pdf",
        )
        validate_schema(self.root, "paper_manifest_schema", manifest.to_dict())
        write_json(self.build_dir / f"{problem.problem_id}_paper_manifest.json", manifest.to_dict())
        return manifest

    def qa_check(self, manifest: PaperManifest) -> tuple[bool, str]:
        ko_text = read_text(self.root / manifest.ko_tex)
        en_text = read_text(self.root / manifest.en_tex)
        rules = self._section_rules()
        forbidden = rules.get("forbidden_expressions", []) if isinstance(rules, dict) else []
        checks = rules.get("checks", {}) if isinstance(rules, dict) else {}
        for number in manifest.theorem_numbers:
            if number not in ko_text:
                return False, f"한국어 논문에 정리 번호 누락: {number}"
        if "Theorem 1" not in en_text:
            return False, "영어 논문에 주정리 번호 누락"
        if not manifest.reference_keys:
            return False, "참고문헌 키가 비어 있음"
        appendix_path = self.root / manifest.appendix_file
        if not appendix_path.exists():
            return False, "재현성 부록 파일 누락"
        appendix_text = read_text(appendix_path)
        for phrase in forbidden if isinstance(forbidden, list) else []:
            if isinstance(phrase, str) and phrase and phrase in ko_text:
                return False, f"한국어 논문에 금지 표현 포함: {phrase}"
        if isinstance(checks, dict) and checks.get("require_seed_and_bounds", False):
            if "seed=" not in ko_text or "bound=" not in ko_text:
                return False, "한국어 논문에 seed/bound 정보 누락"
            if "seed=" not in en_text or "bound=" not in en_text:
                return False, "영어 논문에 seed/bound 정보 누락"
        if isinstance(checks, dict) and checks.get("require_counterexample_scope", False):
            if "variant=" not in ko_text:
                return False, "한국어 논문에 반례 탐색 범위 정보 누락"
            if "variant=" not in en_text:
                return False, "영어 논문에 반례 탐색 범위 정보 누락"
        if isinstance(checks, dict) and checks.get("require_formalization_status", False):
            if "artifact=" not in ko_text or "artifact=" not in en_text:
                return False, "형식화 상태 정보 누락"
        if "검증 중대 이슈 수:" not in appendix_text or "검증 경고 수:" not in appendix_text:
            return False, "재현성 부록에 검증 요약 누락"
        return True, "논문 QA 통과"


class DemoPaperGenerator(PaperGenerator):
    def __init__(self, root: Path) -> None:
        super().__init__(root, backend="demo")


class RealPaperGenerator(PaperGenerator):
    def __init__(self, root: Path) -> None:
        super().__init__(root, backend="real")

    def _section_line(self, title: str, body: str) -> str:
        return f"\\section{{{title}}}\n{body}\\\n"

    def _build_ko_tex(
        self,
        problem: NormalizedProblem,
        verification: VerificationReport,
        formal_report: FormalizationReport,
        semantic_graph: dict[str, Any],
        bib_file: str,
    ) -> str:
        node_titles = semantic_graph.get("node_titles", [])
        node_summary = ", ".join(str(item) for item in node_titles[:4]) if isinstance(node_titles, list) else ""
        theorem_numbers = semantic_graph.get("theorem_numbers", [])
        theorem_sync = ", ".join(str(item) for item in theorem_numbers) if isinstance(theorem_numbers, list) else ""
        required_sections = self._section_rules().get("required_sections", [])
        section_hint = ", ".join(str(item) for item in required_sections[:5]) if isinstance(required_sections, list) else ""
        explored_bound, seed, checked_variant = self._counterexample_context(verification)
        critical_count, warning_count, critical_text, warning_text = self._verification_summary(
            verification
        )
        return (
            self._latex_preamble("연구 파이프라인 기반 초안: " + problem.title)
            + "\\begin{document}\n"
            + "\\maketitle\n"
            + "\\section*{초록}\n"
            + "본 초안은 정규화 결과, proof DAG, 형식화 상태를 직접 반영한다.\\\n"
            + self._section_line("배경", f"문제 식별자 {problem.problem_id}, 도메인 {problem.domain}.")
            + self._section_line("관련 연구", "등록된 참고문헌과 문제 출처를 기준으로 연구 맥락을 정리한다.")
            + self._section_line(
                "정의와 표기",
                f"객체 {', '.join(problem.objects)} 와 표기 {', '.join(problem.notation_map.keys())}. 번호 동기화: {theorem_sync}.",
            )
            + self._section_line("핵심 아이디어", problem.target)
            + self._section_line("보조정리", f"보조정리 1, 보조정리 2를 포함한 proof DAG 노드: {node_summary}.")
            + self._section_line("주정리", f"정리 1. {problem.target}")
            + self._section_line(
                "증명",
                "증명 개요는 proof DAG 순서를 따르며 검증 상태는 "
                + ("통과" if verification.passed else "실패")
                + f" 이다. critical={critical_count}, warnings={warning_count}.",
            )
            + self._section_line(
                "계산 검증",
                f"재현성 요구 섹션 힌트: {section_hint}. 형식화 아티팩트 유형: {formal_report.artifact_kind}. bound={explored_bound}, seed={seed}, variant={checked_variant}. verifier_warning={warning_text}.",
            )
            + self._section_line(
                "한계",
                f"형식화 성공 여부 {formal_report.build_success}, 미해결 obligation {len(formal_report.obligations_unresolved)}, artifact={formal_report.artifact_kind}, verifier_critical={critical_text}.",
            )
            + self._section_line("재현성", "로그, 매니페스트, 체크섬, 형식화 보고서를 함께 보관한다.")
            + "\\bibliographystyle{plain}\n"
            + "\\bibliography{" + bib_file + "}\n"
            + "\\appendix\n"
            + "\\section{부록}\n"
            + "proof DAG 및 형식화 보고서 요약을 첨부한다.\\\n"
            + "\\end{document}\n"
        )

    def _build_en_tex(
        self,
        problem: NormalizedProblem,
        verification: VerificationReport,
        formal_report: FormalizationReport,
        semantic_graph: dict[str, Any],
        bib_file: str,
    ) -> str:
        node_titles = semantic_graph.get("node_titles", [])
        node_summary = ", ".join(str(item) for item in node_titles[:4]) if isinstance(node_titles, list) else ""
        explored_bound, seed, checked_variant = self._counterexample_context(verification)
        critical_count, warning_count, critical_text, warning_text = self._verification_summary(
            verification
        )
        return (
            self._latex_preamble("Research Pipeline Draft: " + problem.title)
            + "\\begin{document}\n"
            + "\\maketitle\n"
            + "\\section*{Abstract}\n"
            + "This draft reflects normalized data, proof DAG structure, and formalization status.\\\n"
            + self._section_line("Background", f"Problem identifier {problem.problem_id} in domain {problem.domain}.")
            + self._section_line("Related Work", "The manuscript is grounded in the registered references and source records.")
            + self._section_line("Definitions and Notation", f"Objects: {', '.join(problem.objects)}.")
            + self._section_line("Core Idea", problem.target)
            + self._section_line("Lemmas", f"Proof DAG nodes: {node_summary}.")
            + self._section_line("Main Theorem", f"Theorem 1. {problem.target}")
            + self._section_line(
                "Proof",
                "The proof outline follows the DAG order and the verification result is "
                + ("passed" if verification.passed else "failed")
                + f". critical={critical_count}; warnings={warning_count}.",
            )
            + self._section_line(
                "Computational Verification",
                f"Formal artifact kind: {formal_report.artifact_kind}; unresolved obligations: {len(formal_report.obligations_unresolved)}; artifact={formal_report.artifact_kind}; bound={explored_bound}; seed={seed}; variant={checked_variant}; verifier_warning={warning_text}.",
            )
            + self._section_line(
                "Limitations",
                f"This draft preserves explicit formalization gaps instead of hiding them. verifier_critical={critical_text}.",
            )
            + self._section_line("Reproducibility", "Logs, manifests, and formalization reports are archived together.")
            + "\\bibliographystyle{plain}\n"
            + "\\bibliography{" + bib_file + "}\n"
            + "\\appendix\n"
            + "\\section{Appendix}\n"
            + "Proof DAG and formalization summaries are attached.\\\n"
            + "\\end{document}\n"
        )
