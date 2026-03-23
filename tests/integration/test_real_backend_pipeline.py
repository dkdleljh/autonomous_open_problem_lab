from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.orchestrator import Orchestrator
from aopl.core.io_utils import read_yaml, write_yaml


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_real_backend_pipeline_runs_with_relaxed_release_policy(tmp_path):
    project_root = prepare_project_root(tmp_path)
    runtime_file = project_root / "configs" / "global" / "runtime.yaml"
    runtime = read_yaml(runtime_file, default={})
    runtime["engines"] = {
        "counterexample_backend": "real",
        "proof_backend": "real",
        "formalizer_backend": "real",
        "paper_generator_backend": "real",
    }
    runtime["release"] = {
        "allow_demo_release": True,
        "require_formal_build_success": False,
        "require_pdf_build_success": False,
        "require_verification_pass": True,
    }
    write_yaml(runtime_file, runtime)

    raw_file = project_root / "data" / "raw_sources" / "sample_open_problems.json"
    raw_file.write_text(
        """
[
  {
    "title": "실백엔드 통합 파이프라인 테스트",
    "domain": "number_theory",
    "statement": "양의 정수 n에 대해 특정 합동 조건이 유지된다고 가정한다.",
    "assumptions": ["정수 집합에서 합동 연산을 사용한다."],
    "goal": "강한형 명제를 약화형과 보조정리 체인으로 환원한다.",
    "aliases": ["real backend integration"],
    "sources": [
      {
        "name": "integration source",
        "url": "https://example.org/integration",
        "type": "registry",
        "reliability": 0.95
      }
    ],
    "metadata": {
      "demo_mode": true,
      "counterexample_search_spec": {
        "type": "integer_forbidden_residue",
        "modulus": 2,
        "forbidden_residue": 0,
        "start": 1,
        "reason": "짝수 n에서 강한형이 실패한다.",
        "weak_variant_recommendation": "n을 홀수로 제한한다."
      },
      "proof_search_spec": {
        "root_title": "기초 정의 고정",
        "lemma_chain": [
          {
            "title": "짝수 잔여류 분리",
            "statement": "짝수 잔여류를 분리한다."
          },
          {
            "title": "홀수 약화형 환원",
            "statement": "홀수 영역 약화형으로 환원한다."
          }
        ],
        "theorem_title": "주정리 초안",
        "theorem_statement": "홀수 영역에서 목표 명제가 유지됨을 보인다."
      }
    }
  }
]
        """.strip(),
        encoding="utf-8",
    )

    summary = Orchestrator(project_root).run(limit=1)

    assert summary["processed"]
    assert not summary["blocked"]
    item = summary["processed"][0]
    assert item["final_stage"] == "RELEASED"
    assert summary["engine_backends"]["counterexample"] == "real"
    assert item["backend_summary"]["counterexample"] == "real"
    assert item["backend_summary"]["proof"] == "real"
    assert item["backend_summary"]["formalizer"] == "real"
    assert item["paper_manifest"]["backend"] == "real"
    assert item["formalization_report"]["backend"] == "real"
    assert item["submission_manifest"]["backend_summary"]["paper_generator"] == "real"
    assert item["paper_manifest"]["pdf_artifact_kind"] in {"placeholder_pdf", "latex_build"}
