from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aopl.core.io_utils import ensure_dir, now_utc_iso, read_json, sha256_json, slugify, write_json
from aopl.core.schema_utils import validate_schema
from aopl.core.types import PipelineStage, ProblemRecord


class Registry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.registry_dir = ensure_dir(root / "data" / "registry")
        self.registry_file = self.registry_dir / "problem_registry.json"
        self.history_file = self.registry_dir / "status_history.json"

    def _load_registry(self) -> list[dict[str, Any]]:
        try:
            payload = read_json(self.registry_file, default=[])
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            raise ValueError("문제 레지스트리 형식이 잘못되었습니다.")
        validate_schema(self.root, "problem_registry_schema", payload)
        return payload

    def _load_history(self) -> list[dict[str, Any]]:
        try:
            history = read_json(self.history_file, default=[])
        except json.JSONDecodeError:
            return []
        if not isinstance(history, list):
            return []
        normalized_history: list[dict[str, Any]] = []
        for item in history:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            metadata = normalized.get("metadata")
            normalized["metadata"] = metadata if isinstance(metadata, dict) else {}
            normalized_history.append(normalized)
        validate_schema(self.root, "status_history_schema", normalized_history)
        return normalized_history

    def _candidate_to_record(self, candidate: dict[str, Any], index: int) -> ProblemRecord:
        title = candidate.get("title", f"문제_{index}")
        problem_id = f"prob_{slugify(title)}"
        candidate_metadata = dict(candidate.get("metadata", {}))
        provenance = {
            "harvest_batch_id": candidate.get("harvest_batch_id"),
            "harvested_at": candidate.get("harvested_at"),
            "harvest_entry_index": candidate.get("harvest_entry_index"),
            "source_signature": candidate.get("source_signature"),
            "source_hashes": list(candidate.get("source_hashes", [])),
            "candidate_hash": candidate.get("candidate_hash"),
            "registry_record_hash": sha256_json(
                {
                    "problem_id": problem_id,
                    "title": title,
                    "domain": candidate.get("domain", "unknown"),
                    "statement": candidate.get("statement", ""),
                    "goal": candidate.get("goal", ""),
                    "sources": candidate.get("sources", []),
                }
            ),
        }
        candidate_metadata["provenance"] = provenance
        return ProblemRecord(
            problem_id=problem_id,
            title=title,
            domain=candidate.get("domain", "unknown"),
            statement=candidate.get("statement", ""),
            assumptions=list(candidate.get("assumptions", [])),
            goal=candidate.get("goal", ""),
            aliases=list(candidate.get("aliases", [])),
            sources=list(candidate.get("sources", [])),
            status=PipelineStage.REGISTERED,
            metadata=candidate_metadata,
        )

    def register(self, harvested: list[dict[str, Any]]) -> list[ProblemRecord]:
        existing_payload = self._load_registry()
        existing_by_id = {item.get("problem_id"): item for item in existing_payload}
        history = self._load_history()
        records: list[ProblemRecord] = []

        for index, candidate in enumerate(harvested, start=1):
            record = self._candidate_to_record(candidate, index)
            existing = existing_by_id.get(record.problem_id)
            if existing is not None:
                old_status = existing.get("status", PipelineStage.REGISTERED.value)
                merged = record.to_dict()
                merged["status"] = old_status
                merged_metadata = dict(existing.get("metadata", {}))
                merged_metadata.update(dict(merged.get("metadata", {})))
                existing["metadata"] = merged_metadata
                merged["metadata"] = merged_metadata
                existing.update(merged)
            else:
                existing_by_id[record.problem_id] = record.to_dict()
                validate_schema(self.root, "problem_schema", existing_by_id[record.problem_id])
                history.append(
                    {
                        "problem_id": record.problem_id,
                        "from": None,
                        "to": PipelineStage.REGISTERED.value,
                        "timestamp": now_utc_iso(),
                        "reason": "registry bootstrap",
                        "metadata": {
                            "harvest_batch_id": record.metadata.get("provenance", {}).get(
                                "harvest_batch_id"
                            ),
                            "source_signature": record.metadata.get("provenance", {}).get(
                                "source_signature"
                            ),
                        },
                    }
                )
            persisted = existing_by_id[record.problem_id]
            records.append(
                ProblemRecord(
                    problem_id=persisted["problem_id"],
                    title=persisted["title"],
                    domain=persisted["domain"],
                    statement=persisted["statement"],
                    assumptions=list(persisted.get("assumptions", [])),
                    goal=persisted["goal"],
                    aliases=list(persisted.get("aliases", [])),
                    sources=list(persisted.get("sources", [])),
                    status=PipelineStage(persisted.get("status", PipelineStage.REGISTERED.value)),
                    metadata=dict(persisted.get("metadata", {})),
                )
            )

        ordered_payload = [existing_by_id[record.problem_id] for record in records]
        for item in ordered_payload:
            validate_schema(self.root, "problem_schema", item)
        validate_schema(self.root, "problem_registry_schema", ordered_payload)
        validate_schema(self.root, "status_history_schema", history)
        write_json(self.registry_file, ordered_payload)
        write_json(self.history_file, history)
        return records

    def update_status(self, problem_id: str, stage: PipelineStage, reason: str) -> None:
        payload = self._load_registry()
        old_stage = None
        for item in payload:
            if item.get("problem_id") == problem_id:
                old_stage = item.get("status")
                if old_stage == stage.value:
                    return
                item["status"] = stage.value
                break
        write_json(self.registry_file, payload)

        history = self._load_history()
        history.append(
            {
                "problem_id": problem_id,
                "from": old_stage,
                "to": stage.value,
                "timestamp": now_utc_iso(),
                "reason": reason,
                "metadata": {},
            }
        )
        validate_schema(self.root, "problem_registry_schema", payload)
        validate_schema(self.root, "status_history_schema", history)
        write_json(self.history_file, history)
