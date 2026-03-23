from __future__ import annotations

from pathlib import Path

from aopl.core.paths import detect_project_root


def main() -> None:
    root: Path = detect_project_root()
    root.mkdir(parents=True, exist_ok=True)
    print(f"바탕화면 프로젝트 루트를 준비했습니다: {root}")


if __name__ == "__main__":
    main()
