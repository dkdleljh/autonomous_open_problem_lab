from __future__ import annotations

import argparse
from pathlib import Path

from aopl.core.io_utils import read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="문제 레지스트리 스키마 이행 도구")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    registry_file = root / "data" / "registry" / "problem_registry.json"
    payload = read_json(registry_file, default=[])
    if not isinstance(payload, list):
        raise SystemExit("레지스트리 형식이 잘못되었습니다.")

    migrated = []
    for item in payload:
        new_item = dict(item)
        new_item.setdefault("metadata", {})
        new_item["metadata"].setdefault("migration_version", "2026-03")
        migrated.append(new_item)

    write_json(registry_file, migrated)
    print(f"레지스트리 이행 완료: {len(migrated)}건")


if __name__ == "__main__":
    main()
