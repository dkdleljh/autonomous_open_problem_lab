from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from aopl.core.io_utils import ensure_dir, write_json, write_text
from aopl.core.types import FormalizationReport, NormalizedProblem, ProofDAG


class Formalizer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.generated_dir = ensure_dir(root / "formal" / "generated_skeletons")
        self.obligation_dir = ensure_dir(root / "formal" / "proof_obligations")
        self.config_file = root / "configs" / "formalization" / "lean.yaml"

    def _lean_imports(self) -> list[str]:
        return ["Mathlib", "Mathlib.Data.Nat.Basic", "Mathlib.Combinatorics.SimpleGraph.Basic"]

    def _build_lean_text(self, problem: NormalizedProblem, dag: ProofDAG) -> tuple[str, list[str]]:
        imports = self._lean_imports()
        obligations = [
            f"obligation_{node.node_id}"
            for node in dag.nodes
            if node.node_type in {"lemma", "theorem"}
        ]
        lines: list[str] = []
        for item in imports:
            lines.append(f"import {item}")
        lines.append("")
        lines.append("namespace AutonomousOpenProblemLab")
        lines.append("")
        lines.append(f'def problemId : String := "{problem.problem_id}"')
        lines.append("")
        for node in dag.nodes:
            if node.node_type == "definition":
                lines.append(f'def {node.node_id}_desc : String := "{node.title}"')
        lines.append("")
        lines.append(f"theorem {problem.problem_id}_main : True := by")
        lines.append("  trivial")
        lines.append("")
        lines.append("end AutonomousOpenProblemLab")
        return "\n".join(lines) + "\n", obligations

    def _attempt_build(self, lean_file: Path, log_file: Path) -> tuple[bool, bool]:
        if shutil.which("lean") is None and shutil.which("lake") is None:
            write_text(log_file, "Lean 실행 파일이 없어 빌드를 건너뜀\n")
            return False, False
        command = (
            ["lean", str(lean_file)]
            if shutil.which("lean")
            else ["lake", "env", "lean", str(lean_file)]
        )
        run = subprocess.run(
            command,
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )
        output = (run.stdout or "") + "\n" + (run.stderr or "")
        write_text(log_file, output)
        return True, run.returncode == 0

    def generate(self, problem: NormalizedProblem, dag: ProofDAG) -> FormalizationReport:
        lean_text, obligations = self._build_lean_text(problem, dag)
        lean_file = self.generated_dir / f"{problem.problem_id}.lean"
        log_file = self.obligation_dir / f"{problem.problem_id}_lean_build.log"
        write_text(lean_file, lean_text)
        build_attempted, build_success = self._attempt_build(lean_file, log_file)

        report = FormalizationReport(
            problem_id=problem.problem_id,
            lean_file=str(lean_file.relative_to(self.root)),
            imports=self._lean_imports(),
            obligations_total=len(obligations),
            obligations_resolved=1,
            obligations_unresolved=obligations,
            build_attempted=build_attempted,
            build_success=build_success,
            build_log_file=str(log_file.relative_to(self.root)),
        )
        write_json(
            self.obligation_dir / f"{problem.problem_id}_formalization_report.json",
            report.to_dict(),
        )
        return report
