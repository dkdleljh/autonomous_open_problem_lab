from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.core.io_utils import read_text, read_yaml, write_yaml
from aopl.core.types import PipelineStage, ProblemRecord
from aopl.services.engine_factory import EngineFactory


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_real_formalizer_generates_structured_skeleton(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["formalizer_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_formalizer",
        title="실백엔드 형식화 테스트",
        domain="graph_theory",
        statement="그래프 구조 형식화 테스트",
        assumptions=["그래프는 유한하다."],
        goal="정리 후보를 Lean 스켈레톤으로 표현한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={},
    )

    normalized = Normalizer(project_root).normalize(record)
    proof_engine = EngineFactory(project_root, {"engines": {"proof_backend": "real"}}).proof_engine()
    dag = proof_engine.build(normalized)
    formalizer = EngineFactory(project_root).formalizer()
    report = formalizer.generate(normalized, dag)

    lean_text = read_text(project_root / report.lean_file)
    assert report.artifact_kind in {"structured_skeleton", "lean_build"}
    assert report.backend == "real"
    assert "theorem prob_real_formalizer_n1 : True := by" in lean_text
    assert "namespace AutonomousOpenProblemLab" in lean_text


def test_real_formalizer_uses_domain_imports(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["formalizer_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_formalizer_imports",
        title="실백엔드 import 테스트",
        domain="number_theory",
        statement="정수론 구조 형식화 테스트",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="정수론 관련 힌트를 import 한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={},
    )

    normalized = Normalizer(project_root).normalize(record)
    proof_engine = EngineFactory(project_root, {"engines": {"proof_backend": "real"}}).proof_engine()
    dag = proof_engine.build(normalized)
    formalizer = EngineFactory(project_root).formalizer()
    report = formalizer.generate(normalized, dag)

    lean_text = read_text(project_root / report.lean_file)
    assert report.backend == "real"
    assert "import Mathlib.Data.Int.Basic" in lean_text


def test_real_formalizer_respects_disabled_build_setting(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["formalizer_backend"] = "real"
    write_yaml(runtime_file, runtime)

    lean_config_file = project_root / "configs" / "formalization" / "lean.yaml"
    lean_config = read_yaml(lean_config_file, default={})
    lean_config.setdefault("build", {})
    lean_config["build"]["try_build"] = False
    write_yaml(lean_config_file, lean_config)

    record = ProblemRecord(
        problem_id="prob_real_formalizer_no_build",
        title="실백엔드 빌드 비활성 테스트",
        domain="number_theory",
        statement="정수론 구조 형식화 테스트",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="빌드 비활성 설정을 따른다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={},
    )

    normalized = Normalizer(project_root).normalize(record)
    proof_engine = EngineFactory(project_root, {"engines": {"proof_backend": "real"}}).proof_engine()
    dag = proof_engine.build(normalized)
    formalizer = EngineFactory(project_root).formalizer()
    report = formalizer.generate(normalized, dag)

    build_log = read_text(project_root / report.build_log_file)
    assert report.build_attempted is False
    assert report.build_success is False
    assert "비활성화" in build_log
