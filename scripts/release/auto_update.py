from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from release_common import (
    doctor_report_hint,
    incident_summary_hint,
    load_incident_summary,
    summarize_doctor_failure,
)


def run(command: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def require_success(code: int, command: list[str], stderr: str, stdout: str, *, repo: Path) -> None:
    if code != 0:
        message = stderr or stdout or "알 수 없는 오류"
        if command[:4] == [command[0], "-m", "aopl", "doctor"]:
            doctor_summary = summarize_doctor_failure(stdout)
            if doctor_summary:
                message = f"{message}\n{doctor_summary}\n{doctor_report_hint(repo)}"
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{message}")


def enforce_incident_policy(repo: Path, *, block_on_permanent: bool) -> None:
    summary = load_incident_summary(repo)
    if not summary:
        return
    blocked_count = int(summary.get("blocked_count", 0))
    failure_class_summary = summary.get("failure_class_summary", {})
    permanent_count = 0
    if isinstance(failure_class_summary, dict):
        permanent_count = int(failure_class_summary.get("permanent", 0))
    if blocked_count <= 0:
        return
    if block_on_permanent and permanent_count > 0:
        raise RuntimeError(
            "incident summary 에 permanent 실패가 포함되어 자동 업데이트를 중단합니다.\n"
            f"{incident_summary_hint(repo)}"
        )
    print(
        "incident summary 경고: "
        f"blocked_count={blocked_count}, permanent_count={permanent_count}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="변경사항 자동 검증, 커밋, 푸시 도구")
    parser.add_argument("--python", default="python3")
    parser.add_argument("--message", default="chore: 자동 업데이트 반영")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--tag-release", action="store_true")
    parser.add_argument("--release-mode", choices=["local", "github"], default="local")
    parser.add_argument("--allow-blocked-transient", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    commands = [
        [args.python, "-m", "aopl", "doctor", "--root", ".", "--profile", "local", "--strict"],
        [args.python, "-m", "pytest", "-q"],
        [args.python, "-m", "aopl", "run-all", "--limit", "1"],
        ["git", "add", "-A"],
    ]

    for command in commands:
        code, out, err = run(command, repo)
        require_success(code, command, err, out, repo=repo)

    enforce_incident_policy(repo, block_on_permanent=not args.allow_blocked_transient)

    code_diff, _, _ = run(["git", "diff", "--cached", "--quiet"], repo)
    if code_diff != 0:
        code_commit, out_commit, err_commit = run(["git", "commit", "-m", args.message], repo)
        require_success(
            code_commit,
            ["git", "commit", "-m", args.message],
            err_commit,
            out_commit,
            repo=repo,
        )

    if args.push:
        code_push, out_push, err_push = run(["git", "push", "origin", "main"], repo)
        require_success(
            code_push,
            ["git", "push", "origin", "main"],
            err_push,
            out_push,
            repo=repo,
        )

    if args.tag_release:
        release_command = [
            args.python,
            "scripts/release/create_release.py",
            "--mode",
            args.release_mode,
            "--bump",
            "patch",
        ]
        if args.allow_blocked_transient:
            release_command.append("--allow-operational-risk")
        code_rel, out_rel, err_rel = run(
            release_command,
            repo,
        )
        require_success(
            code_rel,
            release_command,
            err_rel,
            out_rel,
            repo=repo,
        )

    print("자동 업데이트 완료")


if __name__ == "__main__":
    main()
