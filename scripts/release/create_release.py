from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from release_common import load_incident_summary, summarize_doctor_failure


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or "실행 실패"
        if command[:4] == [command[0], "-m", "aopl", "doctor"]:
            doctor_summary = summarize_doctor_failure(stdout)
            if doctor_summary:
                detail = f"{detail}\n{doctor_summary}"
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{detail}")
    return result.stdout.strip()


def run_optional(command: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()
def detect_github_token(repo: Path) -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    code, out, _ = run_optional(["gh", "auth", "token"], repo)
    if code == 0 and out:
        return out
    return ""


def detect_github_repository(repo: Path) -> str:
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if repository:
        return repository
    code, out, _ = run_optional(["git", "remote", "get-url", "origin"], repo)
    if code != 0 or not out:
        return ""
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$", out)
    if not match:
        return ""
    return f"{match.group(1)}/{match.group(2)}"


def parse_version(tag: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
    if not match:
        return 0, 0, 0
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(version: tuple[int, int, int], bump: str) -> tuple[int, int, int]:
    major, minor, patch = version
    if bump == "major":
        return major + 1, 0, 0
    if bump == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def latest_tag(repo: Path) -> str:
    code, out, _ = run_optional(["git", "tag", "--list", "v*"], repo)
    if code != 0 or not out:
        return "v0.0.0"
    tags = [line.strip() for line in out.splitlines() if line.strip()]
    tags.sort(key=parse_version)
    return tags[-1] if tags else "v0.0.0"


def ensure_repo(repo: Path) -> None:
    if not (repo / ".git").exists():
        raise RuntimeError("Git 저장소가 초기화되지 않았습니다.")
def ensure_release_incident_policy(repo: Path, *, allow_transient_only: bool) -> None:
    summary = load_incident_summary(repo)
    if not summary:
        return
    blocked_count = int(summary.get("blocked_count", 0))
    if blocked_count <= 0:
        return
    failure_class_summary = summary.get("failure_class_summary", {})
    transient_count = 0
    permanent_count = 0
    if isinstance(failure_class_summary, dict):
        transient_count = int(failure_class_summary.get("transient", 0))
        permanent_count = int(failure_class_summary.get("permanent", 0))
    if permanent_count > 0:
        raise RuntimeError("incident summary 에 permanent 실패가 있어 릴리즈를 중단합니다.")
    if blocked_count > 0 and not allow_transient_only:
        raise RuntimeError("incident summary 에 blocked 문제가 있어 릴리즈를 중단합니다.")
    print(
        "incident summary 확인: "
        f"blocked_count={blocked_count}, transient_count={transient_count}, permanent_count={permanent_count}"
    )


def verify_before_release(repo: Path, python_exec: str) -> None:
    mode = os.environ.get("AOPL_RELEASE_MODE", "local")
    profile = "github_release" if mode == "github" else "local"
    run(
        [python_exec, "-m", "aopl", "doctor", "--root", ".", "--profile", profile, "--strict"], repo
    )
    run([python_exec, "-m", "pytest", "-q"], repo)
    run([python_exec, "-m", "aopl", "run-all", "--limit", "1"], repo)
    ensure_release_incident_policy(repo, allow_transient_only=False)


def generate_release_notes(
    repo: Path,
    python_exec: str,
    new_tag: str,
    notes_file: Path,
    *,
    allow_operational_risk: bool,
) -> None:
    command = [
        python_exec,
        "scripts/release/generate_release_notes.py",
        "--tag",
        new_tag,
        "--output",
        str(notes_file.relative_to(repo)),
        "--fail-on-risk",
    ]
    if allow_operational_risk:
        command.append("--allow-risk-override")
    run(command, repo)


def push_release(repo: Path, new_tag: str, mode: str, notes_file: Path) -> None:
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    if branch != "main":
        raise RuntimeError("릴리즈는 main 브랜치에서만 수행할 수 있습니다.")
    run(["git", "push", "origin", "main"], repo)
    run(["git", "push", "origin", new_tag], repo)
    if mode == "github":
        token = detect_github_token(repo)
        repository = detect_github_repository(repo)
        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN 환경변수 또는 gh 로그인 세션이 없어 GitHub 릴리즈를 생성할 수 없습니다."
            )
        if not repository:
            raise RuntimeError(
                "GITHUB_REPOSITORY 환경변수 또는 origin 원격 정보가 없어 GitHub 릴리즈를 생성할 수 없습니다."
            )
        os.environ["GITHUB_TOKEN"] = token
        os.environ["GITHUB_REPOSITORY"] = repository
        run(
            [
                "gh",
                "release",
                "create",
                new_tag,
                "--title",
                f"Autonomous Open Problem Lab {new_tag}",
                "--notes-file",
                str(notes_file),
            ],
            repo,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="자동 버전, 태그, 릴리즈 노트 생성 도구")
    parser.add_argument("--mode", choices=["local", "github"], default="local")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    parser.add_argument("--python", default="python3")
    parser.add_argument("--allow-operational-risk", action="store_true")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    ensure_repo(repo)
    os.environ["AOPL_RELEASE_MODE"] = args.mode
    verify_before_release(repo, args.python)

    current = parse_version(latest_tag(repo))
    next_ver = bump_version(current, args.bump)
    new_tag = f"v{next_ver[0]}.{next_ver[1]}.{next_ver[2]}"

    release_dir = repo / "data" / "paper_assets" / "releases"
    release_dir.mkdir(parents=True, exist_ok=True)
    notes_file = release_dir / f"release_notes_{new_tag}.md"
    generate_release_notes(
        repo,
        args.python,
        new_tag,
        notes_file,
        allow_operational_risk=args.allow_operational_risk,
    )

    run(["git", "add", "-A"], repo)
    code, out, err = run_optional(["git", "diff", "--cached", "--quiet"], repo)
    if code == 0:
        print("스테이징된 변경이 없어 새 릴리즈 커밋을 만들지 않습니다.")
    else:
        run(["git", "commit", "-m", f"release: {new_tag} 자동 릴리즈 준비"], repo)

    run(["git", "tag", "-a", new_tag, "-m", f"{new_tag} 릴리즈"], repo)

    if args.mode == "github":
        push_release(repo, new_tag, args.mode, notes_file)
    else:
        code_remote, _, _ = run_optional(["git", "remote", "get-url", "origin"], repo)
        if code_remote == 0:
            push_release(repo, new_tag, args.mode, notes_file)
        else:
            print(
                "origin 원격이 없어 로컬 태그와 노트만 생성했습니다. "
                "원격 연결 후 수동 push를 진행하세요."
            )

    print(f"릴리즈 준비 완료: {new_tag}")


if __name__ == "__main__":
    main()
