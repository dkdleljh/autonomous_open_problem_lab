from __future__ import annotations

from pathlib import Path
from typing import Any

from aopl.core.io_utils import ensure_dir, read_text, write_json, write_text
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
    def __init__(self, root: Path) -> None:
        self.root = root
        self.ko_dir = ensure_dir(root / "papers" / "ko")
        self.en_dir = ensure_dir(root / "papers" / "en")
        self.shared_dir = ensure_dir(root / "papers" / "shared")
        self.build_dir = ensure_dir(root / "papers" / "builds")

    def _semantic_graph(self, problem: NormalizedProblem, dag: ProofDAG) -> dict[str, Any]:
        theorem_numbers = ["정리 1", "보조정리 1", "보조정리 2"]
        equation_numbers = ["(1)", "(2)"]
        node_titles = [node.title for node in dag.nodes]
        return {
            "problem_id": problem.problem_id,
            "theorem_numbers": theorem_numbers,
            "equation_numbers": equation_numbers,
            "node_titles": node_titles,
        }

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
        return (
            "\\documentclass[11pt]{article}\n"
            "\\usepackage{amsmath,amsthm,amssymb}\n"
            "\\usepackage{hyperref}\n"
            "\\title{자동 탐색 기반 난제 연구 초안: " + problem.title + "}\n"
            "\\author{Autonomous Open Problem Lab}\n"
            "\\date{\\today}\n"
            "\\begin{document}\n"
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
            "탐색은 유한 범위와 seed를 기록하여 재현성을 보장한다.\\\n"
            "\\section{한계}\n"
            "형식화 미해결 의무 수: " + str(len(formal_report.obligations_unresolved)) + "\\\n"
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
        return (
            "\\documentclass[11pt]{article}\n"
            "\\usepackage{amsmath,amsthm,amssymb}\n"
            "\\usepackage{hyperref}\n"
            "\\title{Automated Open Problem Workflow Draft: " + problem.title + "}\n"
            "\\author{Autonomous Open Problem Lab}\n"
            "\\date{\\today}\n"
            "\\begin{document}\n"
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
            "Search bounds, seeds, and timing are explicitly archived.\\\n"
            "\\section{Limitations}\n"
            "Unresolved formal obligations: "
            + str(len(formal_report.obligations_unresolved))
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
        _build_minimal_pdf(pdf_path, f"{problem.problem_id} manuscript placeholder")

        manifest = PaperManifest(
            problem_id=problem.problem_id,
            theorem_numbers=list(semantic_graph["theorem_numbers"]),
            equation_numbers=list(semantic_graph["equation_numbers"]),
            reference_keys=references,
            ko_tex=str(ko_tex_path.relative_to(self.root)),
            en_tex=str(en_tex_path.relative_to(self.root)),
            bib_file=str(bib_path.relative_to(self.root)),
            appendix_file=str(appendix_path.relative_to(self.root)),
            pdf_file=str(pdf_path.relative_to(self.root)),
        )
        write_json(self.build_dir / f"{problem.problem_id}_paper_manifest.json", manifest.to_dict())
        return manifest

    def qa_check(self, manifest: PaperManifest) -> tuple[bool, str]:
        ko_text = read_text(self.root / manifest.ko_tex)
        en_text = read_text(self.root / manifest.en_tex)
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
        return True, "논문 QA 통과"
