from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(command: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def require_success(code: int, command: list[str], stderr: str, stdout: str) -> None:
    if code != 0:
        message = stderr or stdout or "알 수 없는 오류"
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="변경사항 자동 검증, 커밋, 푸시 도구")
    parser.add_argument("--python", default="python3")
    parser.add_argument("--message", default="chore: 자동 업데이트 반영")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--tag-release", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    commands = [
        [args.python, "-m", "pytest", "-q"],
        [args.python, "-m", "aopl", "run-all", "--limit", "1"],
        ["git", "add", "-A"],
    ]

    for command in commands:
        code, out, err = run(command, repo)
        require_success(code, command, err, out)

    code_diff, _, _ = run(["git", "diff", "--cached", "--quiet"], repo)
    if code_diff != 0:
        code_commit, out_commit, err_commit = run(["git", "commit", "-m", args.message], repo)
        require_success(code_commit, ["git", "commit", "-m", args.message], err_commit, out_commit)

    if args.push:
        code_push, out_push, err_push = run(["git", "push", "origin", "main"], repo)
        require_success(code_push, ["git", "push", "origin", "main"], err_push, out_push)

    if args.tag_release:
        code_rel, out_rel, err_rel = run(
            [
                args.python,
                "scripts/release/create_release.py",
                "--mode",
                "local",
                "--bump",
                "patch",
            ],
            repo,
        )
        require_success(
            code_rel,
            [
                args.python,
                "scripts/release/create_release.py",
                "--mode",
                "local",
                "--bump",
                "patch",
            ],
            err_rel,
            out_rel,
        )

    print("자동 업데이트 완료")


if __name__ == "__main__":
    main()
