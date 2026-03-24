from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_under_root(root: Path, relative_path: str | Path) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError("프로젝트 내부 경로에는 절대 경로를 사용할 수 없습니다.")
    normalized = (root / candidate).resolve()
    root_resolved = root.resolve()
    try:
        normalized.relative_to(root_resolved)
    except ValueError as error:
        raise ValueError("프로젝트 루트 밖의 경로는 허용되지 않습니다.") from error
    return normalized


def now_utc_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def parse_utc_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def slugify(value: str) -> str:
    safe = []
    for char in value.lower().strip():
        if char.isalnum() or char == "_":
            safe.append(char)
        elif char in {" ", "-", "/"}:
            safe.append("_")
    compact = "".join(safe)
    while "__" in compact:
        compact = compact.replace("__", "_")
    return compact.strip("_")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_yaml(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
        if data is None:
            return default
        return data


def write_yaml(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(payload, file, allow_unicode=True, sort_keys=False)


def sha256_file(path: Path) -> str:
    hash_obj = hashlib.sha256()
    with path.open("rb") as file:
        while True:
            chunk = file.read(8192)
            if not chunk:
                break
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def sha256_json(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as file:
        file.write(text)


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as file:
        return file.read()


def escape_latex_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    escaped = []
    for char in value:
        escaped.append(replacements.get(char, char))
    return "".join(escaped)


def escape_lean_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", " ")
        .replace("\n", " ")
    )


def escape_lean_comment(value: str) -> str:
    return value.replace("-/", "- /").replace("/-", "/ -").replace("\r", " ").replace("\n", " ")
