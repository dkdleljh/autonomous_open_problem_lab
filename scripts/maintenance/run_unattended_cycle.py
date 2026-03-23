from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="완전 무인 주기 실행 도구")
    parser.add_argument("--python", default="python3")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    cmd = [args.python, "-m", "aopl", "run-all", "--limit", str(args.limit)]
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        raise SystemExit("무인 주기 실행이 실패했습니다.")
    print("무인 주기 실행 완료")


if __name__ == "__main__":
    main()
