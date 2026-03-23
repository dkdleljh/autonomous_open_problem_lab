# 프로그램 사용설명서

## 1. 이 문서의 대상

이 문서는 처음 사용하는 개발자와 연구자를 대상으로 한다. 파이썬 환경 구성부터 전체 자동 파이프라인 실행, 결과 해석, 자동 릴리즈까지 단계별로 설명한다.

## 2. 설치

### 2.1 준비

- Python 3.11 이상
- Git
- 선택 사항: Lean 4, Rust, GitHub CLI

### 2.2 의존성 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .[dev]
```

## 3. 첫 실행

```bash
.venv/bin/aopl run-all --root . --limit 1
```

실행이 끝나면 `data/audit_logs/last_run_summary.json`을 열어 최종 단계와 차단 사유를 확인한다.

## 4. 설정 방법

설정은 `configs/` 아래 YAML 파일로 관리한다.

- 런타임: `configs/global/runtime.yaml`
- 큐 정책: `configs/global/queue.yaml`
- 점수 가중치: `configs/scoring/default.yaml`
- 형식화 임계값: `configs/formalization/obligation_thresholds.yaml`
- 논문 규칙: `configs/paper/*.yaml`

설정 변경 후에는 아래 명령으로 즉시 검증한다.

```bash
.venv/bin/pytest -q
.venv/bin/aopl run-all --root . --limit 1
```

## 5. 단계별 실행

```bash
.venv/bin/aopl harvest --root .
.venv/bin/aopl normalize --root .
.venv/bin/aopl score --root .
.venv/bin/aopl counterexample --root .
.venv/bin/aopl proof --root .
.venv/bin/aopl verify --root .
.venv/bin/aopl formalize --root .
.venv/bin/aopl paper --root .
.venv/bin/aopl submission --root .
```

## 6. 로그 확인

- 전체 단계 감사 로그: `data/audit_logs/pipeline_audit.jsonl`
- 검증 로그: `data/audit_logs/verification_log.jsonl`
- 최종 요약: `data/audit_logs/last_run_summary.json`

## 6.1 운영 준비도 점검

```bash
.venv/bin/aopl doctor --root .
.venv/bin/aopl doctor --root . --profile local --strict
```

이 명령은 다음을 점검한다.

- Git 저장소와 origin 원격 존재 여부
- 현재 브랜치와 워킹트리 상태
- pytest, Lean, Lake, LaTeX, GitHub CLI 설치 여부
- `GITHUB_TOKEN`, `GITHUB_REPOSITORY` 환경변수
- 핵심 한글 문서 존재 여부
- GitHub CI/Release 워크플로우 존재 여부

주의:

- 이 점수는 운영 준비도 점수다.
- "모든 수학 난제를 해결할 수 있는가"를 점수화하는 명령은 아니다.
- `--strict`를 붙이면 활성 프로필의 필수 점검 항목을 모두 만족해야 종료 코드 0이 나온다.
- 프로필은 `local`, `ci`, `github_release`를 지원한다.
- `github_release` 프로필에서는 `GITHUB_TOKEN`, `GITHUB_REPOSITORY`가 없더라도 `gh auth token`과 `origin` 원격 URL이 있으면 자동으로 대체 판단한다.

## 7. 결과 해석 방법

### 7.1 점수 해석

`data/normalized/*_score.json`에서 다섯 지표와 최종 점수를 확인한다.

### 7.2 반례 탐색 해석

`data/experiments/*_counterexample.json`에서 다음 항목을 확인한다.

- 반례 발견 여부
- 탐색 범위
- seed
- 실행 시간
- 약화형 권고

### 7.3 검증 해석

`data/theorem_store/*_verification.json`에서 `critical_issues`가 비어 있어야 검증 통과다.

## 8. 논문 출력 확인

- 한국어 텍스트: `papers/ko/*.tex`
- 영어 텍스트: `papers/en/*.tex`
- 참고문헌: `papers/shared/*.bib`
- 부록: `papers/shared/*_appendix.md`
- PDF: `papers/builds/*.pdf`

논문 번호 동기화는 `aopl/apps/paper_generator.py`의 QA 단계에서 자동 검사한다.

## 9. 자동 릴리즈 동작 방식

### 9.1 로컬 릴리즈

```bash
python3 scripts/release/create_release.py --mode local --bump patch
```

기능:

- `doctor --profile local --strict`로 운영 준비도 100점 확인
- 테스트 실행
- 파이프라인 샘플 실행
- 버전 계산
- 태그 생성
- 릴리즈 노트 생성

### 9.2 GitHub 릴리즈

환경변수 설정:

- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY`

명령:

```bash
python3 scripts/release/create_release.py --mode github --bump patch
```

이 경로는 내부적으로 `doctor --profile github_release --strict`를 먼저 실행한다.

## 10. 자주 발생하는 문제와 해결법

### 문제 1: `aopl` 명령을 찾을 수 없음

- 원인: editable 설치 누락
- 해결: `.venv/bin/pip install -e .[dev]`

### 문제 2: Lean 빌드 실패

- 원인: Lean 미설치 또는 PATH 미설정
- 해결: Lean 설치 후 재실행. 미설치 상태에서도 skeleton 생성은 진행되며 보고서에 실패가 기록된다.

### 문제 3: Release Gate 실패

- 원인: 체크섬 또는 매니페스트 누락
- 해결: `aopl submission --root .` 재실행 후 파일 존재 확인

### 문제 4: GitHub 릴리즈 실패

- 원인: 인증 환경변수 누락
- 해결: 토큰과 저장소 환경변수 설정 후 다시 실행
