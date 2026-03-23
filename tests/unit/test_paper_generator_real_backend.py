from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.core.io_utils import read_text, read_yaml, write_yaml
from aopl.core.types import (
    FormalizationReport,
    PipelineStage,
    ProblemRecord,
    ProofDAG,
    ProofNode,
    VerificationReport,
)
from aopl.services.engine_factory import EngineFactory


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_real_paper_generator_writes_backend_reflective_tex(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["paper_generator_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_paper",
        title="실백엔드 논문화 테스트",
        domain="graph_theory",
        statement="논문화 실백엔드 테스트",
        assumptions=["그래프는 유한하다."],
        goal="주정리 구조를 논문화 본문에 반영한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)
    dag = ProofDAG(
        problem_id=record.problem_id,
        backend="real",
        root_node="n0",
        target_node="n2",
        nodes=[
            ProofNode("n0", "definition", "정의와 표기 고정", "기본 정의", [], "ready"),
            ProofNode("n1", "lemma", "도메인 분해 보조정리", "중간 보조정리", ["n0"], "candidate"),
            ProofNode("n2", "theorem", "주정리 초안", "주정리 구조", ["n1"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}, {"from": "n1", "to": "n2"}],
    )
    verification = VerificationReport(
        record.problem_id,
        {"proof": "real", "counterexample": "real"},
        True,
        [],
        [],
        {
            "problem_id": record.problem_id,
            "backend": "real",
            "checked_variant": "strong_variant",
            "found_counterexample": False,
            "counterexample": None,
            "explored_bound": 32,
            "seed": 20260324,
            "elapsed_seconds": 0.1,
            "weak_variant_recommendation": None,
        },
        "ok",
    )
    formal = FormalizationReport(
        record.problem_id,
        "real",
        "formal/generated_skeletons/x.lean",
        ["Mathlib"],
        2,
        0,
        ["ob1", "ob2"],
        False,
        False,
        "formal/proof_obligations/x.log",
        "structured_skeleton",
    )

    generator = EngineFactory(project_root).paper_generator()
    manifest = generator.generate(normalized, dag, verification, formal)
    ko_text = read_text(project_root / manifest.ko_tex)
    en_text = read_text(project_root / manifest.en_tex)
    appendix_text = read_text(project_root / manifest.appendix_file)

    assert "proof DAG 노드" in ko_text
    assert "Formal artifact kind" in en_text
    assert "bound=32" in ko_text
    assert "seed=20260324" in en_text
    assert "artifact=structured_skeleton" in en_text
    assert "critical=0" in ko_text
    assert "verifier_warning=none" in en_text
    assert "검증 중대 이슈 수: 0" in appendix_text
    assert "검증 경고 수: 0" in appendix_text
    assert manifest.backend == "real"
    assert manifest.pdf_artifact_kind in {"placeholder_pdf", "latex_build"}


def test_real_paper_generator_qa_can_pass_with_adjusted_pdf_status(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["paper_generator_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_paper_qa",
        title="실백엔드 논문화 QA 테스트",
        domain="number_theory",
        statement="영문 본문과 번호 동기화 테스트",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="정리 번호와 본문이 유지된다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)
    dag = ProofDAG(
        problem_id=record.problem_id,
        backend="real",
        root_node="n0",
        target_node="n1",
        nodes=[
            ProofNode("n0", "definition", "정의", "정의", [], "ready"),
            ProofNode("n1", "theorem", "주정리 초안", "정리 번호를 유지한다.", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )
    verification = VerificationReport(
        record.problem_id,
        {"proof": "real", "counterexample": "real"},
        True,
        [],
        [],
        {
            "problem_id": record.problem_id,
            "backend": "real",
            "checked_variant": "strong_variant",
            "found_counterexample": False,
            "counterexample": None,
            "explored_bound": 16,
            "seed": 20260324,
            "elapsed_seconds": 0.1,
            "weak_variant_recommendation": None,
        },
        "ok",
    )
    formal = FormalizationReport(
        record.problem_id,
        "real",
        "formal/generated_skeletons/x.lean",
        ["Mathlib"],
        1,
        0,
        ["ob1"],
        False,
        False,
        "formal/proof_obligations/x.log",
        "structured_skeleton",
    )

    generator = EngineFactory(project_root).paper_generator()
    manifest = generator.generate(normalized, dag, verification, formal)
    assert manifest.backend == "real"
    manifest.pdf_build_attempted = True
    manifest.pdf_build_success = True
    manifest.pdf_artifact_kind = "latex_build"
    passed, reason = generator.qa_check(manifest)

    assert passed is True, reason


def test_real_paper_generator_reflects_verifier_findings_in_text_and_appendix(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["paper_generator_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_paper_verifier_findings",
        title="실백엔드 검증 요약 반영 테스트",
        domain="number_theory",
        statement="검증 요약이 본문과 부록에 반영되는지 확인한다.",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="검증 요약 반영을 확인한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)
    dag = ProofDAG(
        problem_id=record.problem_id,
        backend="real",
        root_node="n0",
        target_node="n1",
        nodes=[
            ProofNode("n0", "definition", "정의", "정의", [], "ready"),
            ProofNode("n1", "theorem", "주정리 초안", "정리 번호를 유지한다.", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )
    verification = VerificationReport(
        record.problem_id,
        {"proof": "real", "counterexample": "real"},
        False,
        ["반례 이후 약화형 권고가 proof DAG에 반영되지 않았습니다."],
        ["proof DAG에 반례 탐색 상한 정보가 드러나지 않습니다."],
        {
            "problem_id": record.problem_id,
            "backend": "real",
            "checked_variant": "strong_variant",
            "found_counterexample": True,
            "counterexample": {"n": 4},
            "explored_bound": 16,
            "seed": 20260324,
            "elapsed_seconds": 0.1,
            "weak_variant_recommendation": "n을 홀수로 제한한다.",
        },
        "verification failed",
    )
    formal = FormalizationReport(
        record.problem_id,
        "real",
        "formal/generated_skeletons/x.lean",
        ["Mathlib"],
        1,
        0,
        ["ob1"],
        False,
        False,
        "formal/proof_obligations/x.log",
        "structured_skeleton",
    )

    generator = EngineFactory(project_root).paper_generator()
    manifest = generator.generate(normalized, dag, verification, formal)
    ko_text = read_text(project_root / manifest.ko_tex)
    en_text = read_text(project_root / manifest.en_tex)
    appendix_text = read_text(project_root / manifest.appendix_file)

    assert "critical=1" in ko_text
    assert "warnings=1" in en_text
    assert "verifier_warning=proof DAG에 반례 탐색 상한 정보가 드러나지 않습니다." in ko_text
    assert "verifier_critical=반례 이후 약화형 권고가 proof DAG에 반영되지 않았습니다." in en_text
    assert "검증 중대 이슈 수: 1" in appendix_text
    assert "검증 경고 수: 1" in appendix_text
    assert (
        "검증 중대 이슈 요약: 반례 이후 약화형 권고가 proof DAG에 반영되지 않았습니다."
        in appendix_text
    )


def test_paper_qa_rejects_forbidden_phrase_in_korean(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime.setdefault("engines", {})
    runtime["engines"]["paper_generator_backend"] = "real"
    write_yaml(runtime_file, runtime)

    record = ProblemRecord(
        problem_id="prob_real_paper_forbidden",
        title="금지 표현 QA 테스트",
        domain="number_theory",
        statement="금지 표현 검사",
        assumptions=["정수 집합에서 합동 연산을 사용한다."],
        goal="금지 표현이 있으면 QA가 실패한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
    )
    normalized = Normalizer(project_root).normalize(record)
    dag = ProofDAG(
        problem_id=record.problem_id,
        backend="real",
        root_node="n0",
        target_node="n1",
        nodes=[
            ProofNode("n0", "definition", "정의", "정의", [], "ready"),
            ProofNode("n1", "theorem", "주정리 초안", "금지 표현 검사", ["n0"], "draft"),
        ],
        edges=[{"from": "n0", "to": "n1"}],
    )
    verification = VerificationReport(
        record.problem_id,
        {"proof": "real", "counterexample": "real"},
        True,
        [],
        [],
        {
            "problem_id": record.problem_id,
            "backend": "real",
            "checked_variant": "strong_variant",
            "found_counterexample": False,
            "counterexample": None,
            "explored_bound": 8,
            "seed": 7,
            "elapsed_seconds": 0.1,
            "weak_variant_recommendation": None,
        },
        "ok",
    )
    formal = FormalizationReport(
        record.problem_id,
        "real",
        "formal/generated_skeletons/x.lean",
        ["Mathlib"],
        1,
        0,
        ["ob1"],
        False,
        False,
        "formal/proof_obligations/x.log",
        "structured_skeleton",
    )

    generator = EngineFactory(project_root).paper_generator()
    manifest = generator.generate(normalized, dag, verification, formal)
    ko_path = project_root / manifest.ko_tex
    ko_path.write_text((ko_path.read_text(encoding="utf-8") + "\n자명하다\n"), encoding="utf-8")
    manifest.pdf_build_attempted = True
    manifest.pdf_build_success = True
    manifest.pdf_artifact_kind = "latex_build"

    passed, reason = generator.qa_check(manifest)

    assert passed is False
    assert "금지 표현" in reason
