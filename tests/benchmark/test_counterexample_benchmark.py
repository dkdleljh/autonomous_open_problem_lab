from __future__ import annotations

import shutil
import time
from pathlib import Path

from aopl.apps.counterexample_engine import CounterexampleEngine
from aopl.apps.normalizer import Normalizer
from aopl.core.types import PipelineStage, ProblemRecord


def prepare_project_root(tmp_path: Path) -> Path:
    source_root = Path(__file__).resolve().parents[2]
    root = tmp_path / "autonomous_open_problem_lab"
    root.mkdir(parents=True, exist_ok=True)
    for name in ["configs", "models", "data", "papers", "formal"]:
        shutil.copytree(source_root / name, root / name, dirs_exist_ok=True)
    return root


def test_counterexample_engine_benchmark(tmp_path):
    project_root = prepare_project_root(tmp_path)
    record = ProblemRecord(
        problem_id="prob_bench",
        title="벤치 테스트",
        domain="number_theory",
        statement="합동 조건 테스트",
        assumptions=["정수 사용"],
        goal="약화형 자동 생성",
        aliases=[],
        sources=[
            {"name": "src", "url": "https://example.org", "type": "registry", "reliability": 0.9}
        ],
        status=PipelineStage.REGISTERED,
        metadata={"toy_counterexample_rule": "strong_variant_false_small_n"},
    )
    normalized = Normalizer(project_root).normalize(record)
    start = time.perf_counter()
    report = CounterexampleEngine(project_root).run(normalized, bound=100)
    elapsed = time.perf_counter() - start
    assert report.explored_bound == 100
    assert elapsed < 2.0
