from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        detail = stderr or stdout or "실행 실패"
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{detail}")
    return result.stdout.strip()


def run_optional(command: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


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


def build_release_notes(repo: Path, new_tag: str) -> str:
    previous = latest_tag(repo)
    if previous == "v0.0.0":
        log = run(["git", "log", "--oneline"], repo)
    else:
        log = run(["git", "log", "--oneline", f"{previous}..HEAD"], repo)
    lines = [line for line in log.splitlines() if line.strip()]
    if not lines:
        lines = ["- 변경 내역 없음"]
    else:
        lines = [f"- {line}" for line in lines]
    notes = [
        f"# 릴리즈 {new_tag}",
        "",
        "## 개요",
        "- 완전 무인 자동 수학 난제 탐색 파이프라인 버전 릴리즈",
        "- 품질 게이트와 재현성 아티팩트를 포함",
        "",
        "## 커밋 내역",
        *lines,
    ]
    return "\n".join(notes) + "\n"


def ensure_repo(repo: Path) -> None:
    if not (repo / ".git").exists():
        raise RuntimeError("Git 저장소가 초기화되지 않았습니다.")


def verify_before_release(repo: Path, python_exec: str) -> None:
    run([python_exec, "-m", "pytest", "-q"], repo)
    run([python_exec, "-m", "aopl", "run-all", "--limit", "1"], repo)


def push_release(repo: Path, new_tag: str, mode: str, notes_file: Path) -> None:
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    if branch != "main":
        raise RuntimeError("릴리즈는 main 브랜치에서만 수행할 수 있습니다.")
    run(["git", "push", "origin", "main"], repo)
    run(["git", "push", "origin", new_tag], repo)
    if mode == "github":
        token = os.environ.get("GITHUB_TOKEN", "")
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if not token:
            raise RuntimeError("GITHUB_TOKEN 환경변수가 없어 GitHub 릴리즈를 생성할 수 없습니다.")
        if not repository:
            raise RuntimeError(
                "GITHUB_REPOSITORY 환경변수가 없어 GitHub 릴리즈를 생성할 수 없습니다."
            )
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
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    ensure_repo(repo)
    verify_before_release(repo, args.python)

    current = parse_version(latest_tag(repo))
    next_ver = bump_version(current, args.bump)
    new_tag = f"v{next_ver[0]}.{next_ver[1]}.{next_ver[2]}"

    notes_text = build_release_notes(repo, new_tag)
    release_dir = repo / "data" / "paper_assets" / "releases"
    release_dir.mkdir(parents=True, exist_ok=True)
    notes_file = release_dir / f"release_notes_{new_tag}.md"
    notes_file.write_text(notes_text, encoding="utf-8")

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
