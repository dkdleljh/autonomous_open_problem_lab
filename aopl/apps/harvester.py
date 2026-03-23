from __future__ import annotations

from pathlib import Path
from typing import Any

from aopl.core.io_utils import ensure_dir, now_utc_iso, read_json, slugify, write_json

DEFAULT_SOURCE_PAYLOAD: list[dict[str, Any]] = [
    {
        "title": "그래프 최소 반례 기반 분해 가능성 후보",
        "domain": "graph_theory",
        "statement": (
            "모든 단순 연결 그래프 G에 대해 조건 C가 성립한다는 추측의 "
            "최소 반례 분해 경로가 존재하는지 탐색한다."
        ),
        "assumptions": [
            "그래프는 유한 단순 무방향 그래프이다.",
            "최소 반례는 꼭짓점 수 기준 최소를 사용한다.",
        ],
        "goal": (
            "최소 반례가 존재하면 반드시 특정 분해 불변량을 위반함을 보이는 "
            "보조정리 후보를 생성한다."
        ),
        "aliases": ["최소 반례 분해 추측", "graph minimal counterexample decomposition"],
        "sources": [
            {
                "name": "공개 문제 목록 샘플",
                "url": "https://example.org/open-problems/graph",
                "type": "registry",
                "reliability": 0.9,
            },
            {
                "name": "조합론 서베이 샘플",
                "url": "https://example.org/surveys/combinatorics",
                "type": "survey",
                "reliability": 0.8,
            },
        ],
        "metadata": {
            "tags": ["counterexample", "decomposition", "formalization_friendly"],
            "toy_counterexample_rule": "none",
        },
    },
    {
        "title": "짧은 정수론 합동 조건 약화형 탐색 후보",
        "domain": "number_theory",
        "statement": (
            "양의 정수 n에 대해 특정 합동 조건을 만족하는 구조가 "
            "무한히 존재하는지의 강한형과 약화형을 자동 분해한다."
        ),
        "assumptions": [
            "정수 집합에서 합동 연산을 사용한다.",
            "탐색 범위는 실행 예산 안에서 제한한다.",
        ],
        "goal": "강한형이 반례로 붕괴하면 약화형 명제를 자동 생성하고 후속 증명 탐색으로 이관한다.",
        "aliases": ["합동 약화형 후보", "modular weakening candidate"],
        "sources": [
            {
                "name": "정수론 문제 모음 샘플",
                "url": "https://example.org/open-problems/number-theory",
                "type": "registry",
                "reliability": 0.88,
            }
        ],
        "metadata": {
            "tags": ["modular", "weak_form", "searchable"],
            "toy_counterexample_rule": "strong_variant_false_small_n",
        },
    },
]


class Harvester:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_dir = ensure_dir(root / "data" / "raw_sources")
        self.sample_file = self.raw_dir / "sample_open_problems.json"

    def _bootstrap_source_if_missing(self) -> None:
        if self.sample_file.exists():
            return
        write_json(self.sample_file, DEFAULT_SOURCE_PAYLOAD)

    def harvest(self) -> list[dict[str, Any]]:
        self._bootstrap_source_if_missing()
        loaded = read_json(self.sample_file, default=[])
        if not isinstance(loaded, list):
            raise ValueError("수집 원본 파일 형식이 잘못되어 목록으로 읽을 수 없습니다.")

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in loaded:
            key = slugify(entry.get("title", "")) + "_" + slugify(entry.get("statement", ""))
            if key in seen:
                continue
            seen.add(key)
            payload = dict(entry)
            payload["harvested_at"] = now_utc_iso()
            deduped.append(payload)

        snapshot_name = f"harvest_snapshot_{now_utc_iso().replace(':', '-')}".replace("+00-00", "Z")
        write_json(self.raw_dir / f"{snapshot_name}.json", deduped)
        write_json(self.raw_dir / "latest_harvest.json", deduped)
        return deduped
