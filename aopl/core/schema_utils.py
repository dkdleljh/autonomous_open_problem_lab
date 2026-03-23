from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def _schema_path(root: Path, schema_name: str) -> Path:
    return root / "models" / "schemas" / f"{schema_name}.json"


def load_schema(root: Path, schema_name: str) -> dict[str, Any]:
    path = _schema_path(root, schema_name)
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"스키마가 객체가 아닙니다: {schema_name}")
    return payload


def _schema_registry(root: Path) -> Registry:
    registry = Registry()
    schema_dir = root / "models" / "schemas"
    for path in schema_dir.glob("*.json"):
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            continue
        schema_id = payload.get("$id")
        if isinstance(schema_id, str):
            registry = registry.with_resource(schema_id, Resource.from_contents(payload))
    return registry


def validate_schema(root: Path, schema_name: str, payload: dict[str, Any]) -> None:
    schema = load_schema(root, schema_name)
    validator = Draft202012Validator(schema, registry=_schema_registry(root))
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(part) for part in first.path) or "<root>"
    raise ValueError(f"{schema_name} 검증 실패 at {location}: {first.message}")
