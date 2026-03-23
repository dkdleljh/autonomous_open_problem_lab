from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "명령 실패"
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{detail}")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="릴리즈 노트 자동 생성")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", default="data/paper_assets/releases/release_notes_generated.md")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    log = run(["git", "log", "--oneline", "-n", "30"], root)
    lines = [line for line in log.splitlines() if line.strip()]
    body_lines = [
        f"# 릴리즈 {args.tag}",
        "",
        "## 요약",
        "- 자동 수집, 정규화, 증명 탐색, 검증, 논문화 파이프라인 포함",
        "- 재현성 아티팩트와 제출 패키지 자동 생성",
        "",
        "## 최근 커밋",
    ]
    body_lines.extend([f"- {line}" for line in lines])

    out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
