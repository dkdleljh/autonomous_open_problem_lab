from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from release_common import detect_operational_risks, failed_policy_checks, load_doctor_report, load_incident_summary


def run(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "명령 실패"
        raise RuntimeError(f"명령 실패: {' '.join(command)}\n{detail}")
    return result.stdout.strip()


def build_operational_summary(root: Path) -> list[str]:
    incident_summary = load_incident_summary(root)
    doctor_summary = load_doctor_report(root)
    failure_class_summary = incident_summary.get("failure_class_summary", {})
    policy_failures = failed_policy_checks(doctor_summary)
    risk_lines = ["## 운영 위험", *[f"- {risk}" for risk in detect_operational_risks(root)]]
    if len(risk_lines) == 1:
        risk_lines.append("- 중대 운영 위험 없음")
    strict_passed = doctor_summary.get("strict_passed", "unknown")
    return [
        *risk_lines,
        "",
        "## 운영 상태",
        f"- 최근 blocked 수: {incident_summary.get('blocked_count', 'unknown')}",
        f"- 최근 failure class 요약: {failure_class_summary}",
        f"- doctor strict 통과: {strict_passed}",
        (
            "- doctor 정책 lint 실패 수: "
            f"{doctor_summary.get('policy_lint_summary', {}).get('failed_policy_checks', 'unknown')}"
        ),
        (
            "- doctor 정책 lint 실패 항목: "
            f"{policy_failures if policy_failures else 'none'}"
        ),
        "",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="릴리즈 노트 자동 생성")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", default="data/paper_assets/releases/release_notes_generated.md")
    parser.add_argument("--fail-on-risk", action="store_true")
    parser.add_argument("--allow-risk-override", action="store_true")
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
        *build_operational_summary(root),
        "## 최근 커밋",
    ]
    body_lines.extend([f"- {line}" for line in lines])

    out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    risks = detect_operational_risks(root)
    if args.fail_on_risk and risks and not args.allow_risk_override:
        raise SystemExit(
            "운영 위험이 감지되어 릴리즈 노트 생성 후 중단합니다: " + "; ".join(risks)
        )
    print(str(out))


if __name__ == "__main__":
    main()
