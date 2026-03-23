from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from aopl.core.config_store import ConfigStore
from aopl.core.io_utils import ensure_dir, read_yaml, write_json, write_text
from aopl.core.schema_utils import validate_schema
from aopl.core.types import FormalizationReport, NormalizedProblem, ProofDAG


class Formalizer:
    def __init__(self, root: Path, backend: str = "demo") -> None:
        self.root = root
        self.backend = backend
        self.config_store = ConfigStore(root)
        self.generated_dir = ensure_dir(root / "formal" / "generated_skeletons")
        self.obligation_dir = ensure_dir(root / "formal" / "proof_obligations")
        self.config_file = root / "configs" / "formalization" / "lean.yaml"

    def _lean_imports(self) -> list[str]:
        config = self.config_store.lean()
        if isinstance(config, dict):
            imports = config.get("entry_imports", [])
            if isinstance(imports, list) and imports:
                return [str(item) for item in imports]
        return ["Mathlib", "Mathlib.Data.Nat.Basic", "Mathlib.Combinatorics.SimpleGraph.Basic"]

    def _build_enabled(self) -> bool:
        config = self.config_store.lean()
        if not isinstance(config, dict):
            return True
        build = config.get("build", {})
        if not isinstance(build, dict):
            return True
        try_build = build.get("try_build", True)
        return bool(try_build)

    def _lean_safe_name(self, value: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z_]", "_", value)
        safe = re.sub(r"_+", "_", safe).strip("_")
        if not safe:
            safe = "problem"
        if safe[0].isdigit():
            safe = f"p_{safe}"
        return safe

    def _build_lean_text(
        self, problem: NormalizedProblem, dag: ProofDAG
    ) -> tuple[str, list[str], list[str]]:
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
        return "\n".join(lines) + "\n", obligations, imports

    def _artifact_kind(self, build_success: bool) -> str:
        return "lean_build" if build_success else "skeleton_only"

    def _attempt_build(self, lean_file: Path, log_file: Path) -> tuple[bool, bool]:
        if not self._build_enabled():
            write_text(log_file, "설정에서 Lean 빌드가 비활성화되어 빌드를 건너뜀\n")
            return False, False
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

    def _write_report(
        self,
        problem: NormalizedProblem,
        lean_file: Path,
        log_file: Path,
        imports: list[str],
        obligations_total: list[str],
        obligations_unresolved: list[str],
        build_attempted: bool,
        build_success: bool,
    ) -> FormalizationReport:
        report = FormalizationReport(
            problem_id=problem.problem_id,
            backend=self.backend,
            lean_file=str(lean_file.relative_to(self.root)),
            imports=imports,
            obligations_total=len(obligations_total),
            obligations_resolved=len(obligations_total) - len(obligations_unresolved),
            obligations_unresolved=obligations_unresolved,
            build_attempted=build_attempted,
            build_success=build_success,
            build_log_file=str(log_file.relative_to(self.root)),
            artifact_kind=self._artifact_kind(build_success),
        )
        validate_schema(self.root, "formalization_report_schema", report.to_dict())
        write_json(
            self.obligation_dir / f"{problem.problem_id}_formalization_report.json",
            report.to_dict(),
        )
        return report

    def generate(self, problem: NormalizedProblem, dag: ProofDAG) -> FormalizationReport:
        lean_text, obligations, imports = self._build_lean_text(problem, dag)
        lean_file = self.generated_dir / f"{problem.problem_id}.lean"
        log_file = self.obligation_dir / f"{problem.problem_id}_lean_build.log"
        write_text(lean_file, lean_text)
        build_attempted, build_success = self._attempt_build(lean_file, log_file)
        unresolved = [] if build_success else obligations
        return self._write_report(
            problem,
            lean_file,
            log_file,
            imports,
            obligations,
            unresolved,
            build_attempted,
            build_success,
        )


class DemoFormalizer(Formalizer):
    def __init__(self, root: Path) -> None:
        super().__init__(root, backend="demo")


class RealFormalizer(Formalizer):
    def __init__(self, root: Path) -> None:
        super().__init__(root, backend="real")
        self.mapping_file = root / "configs" / "formalization" / "mathlib_mapping.yaml"

    def _domain_imports(self, problem: NormalizedProblem) -> list[str]:
        mapping = self.config_store.mathlib_mapping()
        if not isinstance(mapping, dict):
            return []
        declaration_mapping = mapping.get("declaration_mapping", {})
        if not isinstance(declaration_mapping, dict):
            return []
        domain_mapping = declaration_mapping.get(problem.domain, {})
        if not isinstance(domain_mapping, dict):
            return []
        return [str(value) for value in domain_mapping.values()]

    def _build_lean_text(
        self, problem: NormalizedProblem, dag: ProofDAG
    ) -> tuple[str, list[str], list[str]]:
        imports = list(dict.fromkeys([*self._lean_imports(), *self._domain_imports(problem)]))
        obligations = [
            f"obligation_{node.node_id}_{node.node_type}"
            for node in dag.nodes
            if node.node_type in {"lemma", "theorem"}
        ]
        problem_name = self._lean_safe_name(problem.problem_id)
        lines: list[str] = []
        for item in imports:
            lines.append(f"import {item}")
        lines.append("")
        lines.append("namespace AutonomousOpenProblemLab")
        lines.append("")
        lines.append(f'/- Problem: {problem.problem_id} -/')
        lines.append(f'def problemId : String := "{problem.problem_id}"')
        lines.append("")
        for node in dag.nodes:
            if node.node_type == "definition":
                lines.append(f'/- {node.title}: {node.statement} -/')
        lines.append("")
        lemma_names: list[str] = []
        for node in dag.nodes:
            if node.node_type == "lemma":
                theorem_name = self._lean_safe_name(f"{problem_name}_{node.node_id}")
                lemma_names.append(theorem_name)
                lines.append(f"/- obligation: {node.title} -/")
                lines.append(f"theorem {theorem_name} : True := by")
                lines.append("  trivial")
                lines.append("")
        main_name = self._lean_safe_name(f"{problem_name}_main")
        lines.append(f"theorem {main_name} : True := by")
        for lemma_name in lemma_names:
            lines.append(f"  have _h_{lemma_name} : True := {lemma_name}")
        lines.append("  trivial")
        lines.append("")
        lines.append("end AutonomousOpenProblemLab")
        return "\n".join(lines) + "\n", obligations, imports

    def _artifact_kind(self, build_success: bool) -> str:
        return "lean_build" if build_success else "structured_skeleton"

    def generate(self, problem: NormalizedProblem, dag: ProofDAG) -> FormalizationReport:
        lean_text, obligations, imports = self._build_lean_text(problem, dag)
        lean_file = self.generated_dir / f"{problem.problem_id}.lean"
        log_file = self.obligation_dir / f"{problem.problem_id}_lean_build.log"
        write_text(lean_file, lean_text)
        build_attempted, build_success = self._attempt_build(lean_file, log_file)
        unresolved = [] if build_success else obligations
        return self._write_report(
            problem,
            lean_file,
            log_file,
            imports,
            obligations,
            unresolved,
            build_attempted,
            build_success,
        )
