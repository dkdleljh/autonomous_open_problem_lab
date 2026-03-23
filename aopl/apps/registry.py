from __future__ import annotations

from pathlib import Path
from typing import Any

from aopl.core.io_utils import ensure_dir, now_utc_iso, read_json, slugify, write_json
from aopl.core.types import PipelineStage, ProblemRecord


class Registry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.registry_dir = ensure_dir(root / "data" / "registry")
        self.registry_file = self.registry_dir / "problem_registry.json"
        self.history_file = self.registry_dir / "status_history.json"

    def register(self, harvested: list[dict[str, Any]]) -> list[ProblemRecord]:
        records: list[ProblemRecord] = []
        for index, candidate in enumerate(harvested, start=1):
            title = candidate.get("title", f"문제_{index}")
            problem_id = f"prob_{slugify(title)}"
            sources = candidate.get("sources", [])
            record = ProblemRecord(
                problem_id=problem_id,
                title=title,
                domain=candidate.get("domain", "unknown"),
                statement=candidate.get("statement", ""),
                assumptions=list(candidate.get("assumptions", [])),
                goal=candidate.get("goal", ""),
                aliases=list(candidate.get("aliases", [])),
                sources=sources,
                status=PipelineStage.REGISTERED,
                metadata=dict(candidate.get("metadata", {})),
            )
            records.append(record)

        write_json(self.registry_file, [record.to_dict() for record in records])
        history = read_json(self.history_file, default=[])
        if not isinstance(history, list):
            history = []
        for record in records:
            history.append(
                {
                    "problem_id": record.problem_id,
                    "from": None,
                    "to": PipelineStage.REGISTERED.value,
                    "timestamp": now_utc_iso(),
                    "reason": "registry bootstrap",
                }
            )
        write_json(self.history_file, history)
        return records

    def update_status(self, problem_id: str, stage: PipelineStage, reason: str) -> None:
        payload = read_json(self.registry_file, default=[])
        if not isinstance(payload, list):
            raise ValueError("문제 레지스트리 형식이 잘못되었습니다.")
        old_stage = None
        for item in payload:
            if item.get("problem_id") == problem_id:
                old_stage = item.get("status")
                item["status"] = stage.value
                break
        write_json(self.registry_file, payload)

        history = read_json(self.history_file, default=[])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "problem_id": problem_id,
                "from": old_stage,
                "to": stage.value,
                "timestamp": now_utc_iso(),
                "reason": reason,
            }
        )
        write_json(self.history_file, history)
