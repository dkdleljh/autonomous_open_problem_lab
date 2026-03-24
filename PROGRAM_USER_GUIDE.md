# 프로그램 사용설명서

## 1. 목적

이 문서는 처음 프로젝트를 실행하는 사람, 파이프라인 결과를 해석해야 하는 사람, 실제로 GitHub 릴리즈까지 운영해야 하는 사람을 위한 실무용 안내서다. "어떻게 설치하는가", "어떤 순서로 실행하는가", "결과를 어디서 읽는가", "문제가 생기면 무엇을 봐야 하는가"를 한 문서에서 설명한다.

## 2. 권장 독자

- 처음 환경을 구성하는 개발자
- 파이프라인 산출물을 읽는 연구자
- CI, Release 운영을 담당하는 관리자
- doctor 기반 100점 운영 준비도를 유지해야 하는 사람

## 3. 설치

### 3.1 기본 요구 사항

- Python 3.11 이상
- Git
- GitHub CLI
- 선택 사항: Lean 4, Lake, LaTeX

### 3.2 Python 환경 구성

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .[dev]
```

### 3.3 도구 설치 점검

```bash
.venv/bin/aopl doctor --root . --profile local
```

## 4. 가장 빠른 실행 경로

```bash
.venv/bin/aopl run-all --root . --limit 1
```

실행 후 확인해야 할 대표 파일은 아래와 같다.

- `data/audit_logs/last_doctor_report.json`
- `data/audit_logs/last_run_summary.json`
- `data/audit_logs/last_incident_summary.json`
- `data/audit_logs/pipeline_audit.jsonl`
- `data/theorem_store/*_verification.json`
- `formal/proof_obligations/*_formalization_report.json`
- `papers/builds/*_paper_manifest.json`

## 5. 단계별 명령

### 5.1 수집

```bash
.venv/bin/aopl harvest --root .
```

### 5.2 정규화

```bash
.venv/bin/aopl normalize --root .
```

### 5.3 점수 계산

```bash
.venv/bin/aopl score --root .
```

### 5.4 반례 탐색

```bash
.venv/bin/aopl counterexample --root .
```

### 5.5 proof DAG 생성

```bash
.venv/bin/aopl proof --root .
```

### 5.6 검증

```bash
.venv/bin/aopl verify --root .
```

### 5.7 형식화

```bash
.venv/bin/aopl formalize --root .
```

### 5.8 논문 생성

```bash
.venv/bin/aopl paper --root .
```

### 5.9 제출 패키지 생성

```bash
.venv/bin/aopl submission --root .
```

## 6. doctor 사용법

### 6.1 기본 점검

```bash
.venv/bin/aopl doctor --root .
```

### 6.2 strict 점검

```bash
.venv/bin/aopl doctor --root . --profile local --strict
```

### 6.3 지원 프로필

- `local`: 로컬 개발 및 무인 실행 준비도
- `ci`: GitHub CI 러너 준비도
- `github_release`: GitHub Release 러너 준비도

### 6.4 strict 의미

`--strict`는 단순 보고용이 아니다. 점수가 모자라거나 필수 항목이 하나라도 실패하면 종료 코드 1로 끝난다. 즉, 자동화 스크립트가 즉시 실패한다.

### 6.5 doctor가 점검하는 항목

- 프로젝트 루트 존재
- Git 저장소 여부
- origin 원격
- 현재 브랜치 또는 tag 상태
- 워킹트리 청결
- pytest 실행 가능 여부
- Lean, Lake, LaTeX, GitHub CLI
- GitHub 인증 및 저장소 식별 가능 여부
- 핵심 한글 문서 존재 여부
- GitHub Actions 워크플로우 존재 여부
- 최근 실행이 있었다면 마지막 incident summary 표시
- 최근 doctor 실행이 있었다면 정책 lint와 strict 결과를 `last_doctor_report.json`으로 보존

### 6.6 GitHub 인증 fallback

`github_release` 프로필에서는 다음 둘 중 하나만 충족해도 된다.

- `GITHUB_TOKEN`, `GITHUB_REPOSITORY` 환경변수
- `gh auth` 로그인 세션 + `origin` 원격 URL

## 7. 결과 해석

### 7.1 registry

- 위치: `data/registry/problem_registry.json`
- 의미: 현재 알고 있는 문제 목록과 현재 단계

### 7.2 normalized

- 위치: `data/normalized/*_normalized.json`
- 의미: 객체, 가정, 목표, 동치형, 약화형, 강화형이 구조화된 결과

### 7.3 score

- 위치: `data/normalized/*_score.json`
- 의미: 선별 점수와 세부 지표

### 7.4 counterexample

- 위치: `data/experiments/*_counterexample.json`
- 의미: 탐색 범위, seed, 발견 여부, 약화형 권고

### 7.5 proof DAG

- 위치: `data/proof_dag/*_proof_dag.json`
- 의미: 증명 개요 구조와 의존 관계

### 7.6 verification

- 위치: `data/theorem_store/*_verification.json`
- 의미: critical issue, warning, gate reason

### 7.7 formalization report

- 위치: `formal/proof_obligations/*_formalization_report.json`
- 의미: Lean 파일, obligation 수, unresolved 목록, build 성공 여부

### 7.8 paper manifest

- 위치: `papers/builds/*_paper_manifest.json`
- 의미: ko/en tex, appendix, pdf, 번호 동기화, pdf build 여부

### 7.9 submission manifest

- 위치: 릴리즈 패키지 내 `submission_manifest.json`
- 의미: 포함 파일, 체크섬, verification summary, artifact summary

### 7.10 incident summary

- 위치: `data/audit_logs/last_incident_summary.json`
- 의미: 최근 실행의 blocked 수, 런타임 예외 수, failure class 요약, 주요 차단 사유

### 7.11 doctor report

- 위치: `data/audit_logs/last_doctor_report.json`
- 의미: 최근 doctor 점수, strict 통과 여부, 활성 프로필, 정책 lint 실패 수와 실패 항목

### 7.12 generated release notes

- 위치: `data/paper_assets/releases/release_notes_generated.md`
- 의미: 최근 커밋뿐 아니라 `incident summary`, `doctor report`를 읽어 운영 위험과 정책 lint 상태를 함께 요약한 GitHub 릴리즈 본문
- 동작: 운영 위험이 감지되면 release workflow는 기본적으로 이 단계에서 실패하며, 수동 `workflow_dispatch`에서만 override를 허용

## 8. 운영 절차

### 8.1 로컬 개발 루프

```bash
.venv/bin/aopl doctor --root . --profile local --strict
.venv/bin/ruff check aopl tests scripts
.venv/bin/pytest -q
.venv/bin/aopl run-all --root . --limit 1
```

### 8.2 자동 업데이트

```bash
python3 scripts/release/auto_update.py --python .venv/bin/python --push
```

`auto_update.py`는 기본적으로 `last_doctor_report.json`, `last_incident_summary.json` 기준으로 보수적으로 실패한다. `--allow-blocked-transient`를 주면 transient blocked를 허용하고, `--tag-release`를 함께 쓸 때는 동일한 의도로 `create_release.py --allow-operational-risk`까지 전달한다.

이 스크립트는 doctor, 테스트, 샘플 실행, 커밋, 선택적 push를 묶는다.

### 8.3 로컬 릴리즈

```bash
python3 scripts/release/create_release.py --mode local --bump patch --python .venv/bin/python
```

### 8.4 GitHub 릴리즈

```bash
python3 scripts/release/create_release.py --mode github --bump patch --python .venv/bin/python
```

이 명령은 내부적으로 다음을 수행한다.

1. `doctor --profile github_release --strict`
2. `pytest -q`
3. `aopl run-all --limit 1`
4. 버전 계산
5. 태그 생성
6. push
7. GitHub Release 생성

## 9. 문제 해결

### 9.1 `aopl` 명령을 찾을 수 없음

- 원인: editable 설치 누락
- 해결: `.venv/bin/pip install -e .[dev]`

### 9.2 doctor strict 실패

- 원인: 워킹트리 dirty, 도구 미설치, 원격/인증 누락
- 해결: 출력 JSON의 `blocking_checks`를 먼저 본다

### 9.3 Lean 또는 Lake 실패

- 원인: PATH 미설정 또는 미설치
- 해결: Lean 설치 후 `doctor` 재실행

### 9.4 PDF 생성 실패

- 원인: LaTeX 미설치 또는 템플릿 오류
- 해결: `papers/builds/*_latex.log`와 `paper_manifest.json`을 같이 확인

### 9.5 GitHub Release 실패

- 원인: 인증 없음, 원격 없음, doctor strict 실패
- 해결: `gh auth status`, `git remote -v`, `aopl doctor --profile github_release --strict`

## 10. 권장 읽기 순서

1. [README.md](./README.md)
2. [PROGRAM_USER_GUIDE.md](./PROGRAM_USER_GUIDE.md)
3. [PROGRAM_DETAILED_DESIGN.md](./PROGRAM_DETAILED_DESIGN.md)
4. [docs/README.md](./docs/README.md)
5. [PROGRAM_REALITY_CHECK_KO.md](./PROGRAM_REALITY_CHECK_KO.md)
