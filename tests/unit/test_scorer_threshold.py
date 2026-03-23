from __future__ import annotations

import shutil
from pathlib import Path

from aopl.apps.normalizer import Normalizer
from aopl.apps.scorer import Scorer
from aopl.core.io_utils import read_yaml, write_yaml
from aopl.core.types import PipelineStage, ProblemRecord


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_scorer_respects_configured_selection_threshold(tmp_path):
    project_root = prepare_project_root(tmp_path)
    config_file = project_root / "configs" / "scoring" / "default.yaml"
    config = read_yaml(config_file, default={})
    config.setdefault("selection", {})
    config["selection"]["min_score"] = 0.99
    write_yaml(config_file, config)

    record = ProblemRecord(
        problem_id="prob_threshold_case",
        title="점수 임계값 테스트",
        domain="number_theory",
        statement="정수 조건의 점수화를 확인한다.",
        assumptions=["정수 연산을 사용한다."],
        goal="약화형 분해 가능성을 점검한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "survey", "reliability": 0.92}
        ],
        status=PipelineStage.REGISTERED,
    )

    normalized = Normalizer(project_root).normalize(record)
    score = Scorer(project_root).score(normalized)

    assert score.score < 0.99
    assert score.selected is False


def test_scorer_applies_domain_priority_boost(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_priority_boost_case",
        title="도메인 우선순위 테스트",
        domain="graph_theory",
        statement="유한 그래프의 점수화를 확인한다.",
        assumptions=["유한 그래프를 사용한다."],
        goal="약화형 분해 가능성을 점검한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "survey", "reliability": 0.92}
        ],
        status=PipelineStage.REGISTERED,
    )

    normalized = Normalizer(project_root).normalize(record)
    score = Scorer(project_root).score(normalized)

    assert score.selected is True
    assert any("도메인 우선순위 배수 1.05" in line for line in score.rationale)


def test_scorer_rejects_disabled_domain(tmp_path):
    project_root = prepare_project_root(tmp_path)
    domain_file = project_root / "configs" / "problems" / "number_theory.yaml"
    domain_config = read_yaml(domain_file, default={})
    domain_config["enabled"] = False
    write_yaml(domain_file, domain_config)

    record = ProblemRecord(
        problem_id="prob_disabled_domain_case",
        title="비활성 도메인 테스트",
        domain="number_theory",
        statement="정수 조건의 점수화를 확인한다.",
        assumptions=["정수 연산을 사용한다."],
        goal="약화형 분해 가능성을 점검한다.",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "survey", "reliability": 0.92}
        ],
        status=PipelineStage.REGISTERED,
    )

    normalized = Normalizer(project_root).normalize(record)
    score = Scorer(project_root).score(normalized)

    assert score.score == 0.0
    assert score.selected is False
    assert any("비활성화" in line for line in score.rationale)
