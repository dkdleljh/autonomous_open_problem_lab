# Autonomous Open Problem Lab

Autonomous Open Problem Lab은 수학 난제 후보를 수집하고, 정규화하고, 우선순위를 계산하고, 반례를 점검하고, proof DAG를 만들고, 검증하고, 형식화와 논문 초안, 제출 패키지, 릴리즈 아티팩트까지 자동으로 이어주는 연구 파이프라인이다.

이 프로젝트의 강점은 "모든 난제를 해결한다"가 아니라, 연구 파이프라인을 무인 운영 가능한 형태로 구조화하고, 모든 중간 산출물과 게이트 판단을 추적 가능하게 남기며, 운영 준비도가 부족하면 실제로 자동 차단한다는 점이다.

## 1. 현재 프로젝트가 하는 일

- 난제 후보 수집과 등록
- 문제 레지스트리 구축과 상태 이력 관리
- 정규화 산출물 생성
- 점수 계산과 선별
- 반례 탐색
- proof DAG 생성
- 검증 리포트 생성
- Lean skeleton 및 형식화 리포트 생성
- 한국어, 영어 논문 초안 생성
- 제출 패키지, 체크섬, 릴리즈 노트 생성
- GitHub CI, Release, doctor 기반 운영 준비도 점검

## 2. 하지 않는 일

- 모든 수학 난제를 자동으로 해결한다고 보장하지 않는다.
- 템플릿 산출물을 실제 수학적 성과와 동일시하지 않는다.
- 형식화 미완료, 논리 공백, 약화형 전환, placeholder PDF 여부를 숨기지 않는다.

이 한계는 [PROGRAM_REALITY_CHECK_KO.md](./PROGRAM_REALITY_CHECK_KO.md)에 더 명확히 정리되어 있다.

## 3. 빠른 시작

### 3.1 설치

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .[dev]
```

### 3.2 전체 파이프라인 실행

```bash
.venv/bin/aopl run-all --root . --limit 1
```

### 3.3 운영 준비도 점검

```bash
.venv/bin/aopl doctor --root . --profile local --strict
```

`doctor --strict`는 활성 프로필에서 요구하는 핵심 항목이 전부 충족되지 않으면 종료 코드 1로 실패한다. 이 경로는 로컬 자동 업데이트, GitHub CI, GitHub Release 워크플로우에서 실제로 사용된다.

## 4. CLI 명령 요약

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
.venv/bin/aopl doctor --root . --profile local --strict
.venv/bin/aopl run-all --root . --limit 1
```

각 명령의 상세 사용법과 결과 해석은 [PROGRAM_USER_GUIDE.md](./PROGRAM_USER_GUIDE.md)를 기준 문서로 본다.

## 5. 주요 아키텍처

### 5.1 파이프라인 단계

`REGISTERED → HARVESTED → NORMALIZED → SCORED → SELECTED → COUNTEREXAMPLE_CHECKED → LEMMA_GRAPH_BUILT → DRAFT_PROOF_CREATED → INTERNAL_VERIFICATION_PASSED → FORMALIZATION_ATTEMPTED → PAPER_DRAFT_GENERATED → PAPER_QA_PASSED → SUBMISSION_PACKAGE_READY → RELEASED`

모든 단계는 품질 게이트를 통과해야 다음 단계로 전이된다. 실패하면 `BLOCKED` 상태와 함께 감사 로그, 상태 이력, 요약 JSON에 사유가 남는다.

### 5.2 핵심 모듈

- `aopl/apps/harvester.py`: 수집 및 provenance 부여
- `aopl/apps/registry.py`: registry merge, 상태 이력, schema 검증
- `aopl/apps/normalizer.py`: normalized problem 생성
- `aopl/apps/scorer.py`: score card 계산
- `aopl/apps/counterexample_engine.py`: demo/real 반례 백엔드
- `aopl/apps/proof_engine.py`: demo/real proof DAG 백엔드
- `aopl/apps/verifier.py`: 검증, consistency check, verification log
- `aopl/apps/formalizer.py`: Lean skeleton, build report
- `aopl/apps/paper_generator.py`: bilingual paper, appendix, PDF build
- `aopl/apps/submission_builder.py`: submission manifest, checksum, bundle
- `aopl/apps/orchestrator.py`: 전체 상태 머신과 감사 로그

### 5.3 데이터 계약

주요 산출물은 JSON Schema로 검증된다.

- problem registry
- status history
- normalized problem
- score card
- counterexample report
- proof DAG
- verification report
- formalization report
- paper manifest
- submission manifest
- stage event
- run summary

관련 schema는 `models/schemas/` 아래에 있다.

## 6. 운영 준비도 100점 정책

이 저장소에서 말하는 "100점"은 과장된 완벽성을 의미하지 않는다. 운영 준비도 점수다. 구체적으로는 아래 의미를 가진다.

- 활성 프로필의 필수 점검 항목이 모두 통과함
- `doctor --strict`가 성공함
- 워킹트리가 clean 상태임
- 원격 저장소와 릴리즈 경로가 실제로 사용 가능함
- 문서, 테스트, CI, Release 자동화가 연결되어 있음

지원 프로필은 다음과 같다.

- `local`: 로컬 무인 운영 준비도
- `ci`: GitHub CI 준비도
- `github_release`: GitHub 릴리즈 준비도

`github_release` 프로필에서는 `GITHUB_TOKEN`, `GITHUB_REPOSITORY`가 비어 있어도 `gh auth` 세션과 `origin` 원격 URL을 통해 자동 판정할 수 있다.

## 7. GitHub 운영 구조

### 7.1 CI

- 파일: `.github/workflows/ci.yml`
- 역할: Ruff, doctor strict, pytest, 샘플 파이프라인 실행, 감사 로그 아티팩트 업로드

### 7.2 Release

- 파일: `.github/workflows/release.yml`
- 역할: doctor strict, pytest, 샘플 파이프라인, 릴리즈 노트 생성, GitHub Release 자산 업로드

### 7.3 로컬 자동화 스크립트

- `scripts/release/create_release.py`: 테스트, doctor, 버전 증가, 태그 생성, 릴리즈 준비
- `scripts/release/auto_update.py`: doctor, 테스트, 샘플 실행, 커밋, 선택적 push 및 태그 릴리즈

## 8. 출력물 위치

- `data/audit_logs/`: 감사 로그와 실행 요약
- `data/registry/`: problem registry, status history
- `data/normalized/`: normalized JSON, score JSON
- `data/experiments/`: counterexample report
- `data/proof_dag/`: proof DAG
- `data/theorem_store/`: verification report
- `formal/generated_skeletons/`: Lean skeleton
- `formal/proof_obligations/`: formalization report
- `papers/ko/`, `papers/en/`: 논문 초안
- `papers/builds/`: PDF와 paper manifest
- `data/paper_assets/releases/`: zip, tar.gz, checksums, release note

각 디렉터리별 세부 의미는 해당 경로의 `README.md`를 참고한다.

## 9. 문서 안내

핵심 문서는 아래 순서로 읽는 것이 좋다.

1. [README.md](./README.md)
2. [PROGRAM_USER_GUIDE.md](./PROGRAM_USER_GUIDE.md)
3. [PROGRAM_DETAILED_DESIGN.md](./PROGRAM_DETAILED_DESIGN.md)
4. [CONTRIBUTING.md](./CONTRIBUTING.md)
5. [CHANGELOG.md](./CHANGELOG.md)
6. [docs/README.md](./docs/README.md)
7. [PROGRAM_REALITY_CHECK_KO.md](./PROGRAM_REALITY_CHECK_KO.md)
8. [PROGRAM_100_SCORE_ROADMAP_KO.md](./PROGRAM_100_SCORE_ROADMAP_KO.md)

## 10. 현재 상태

이 저장소는 현재 다음을 실제로 통과한 상태를 기준으로 운영된다.

- 로컬 `doctor --profile local --strict`
- GitHub `ci` 워크플로우
- GitHub `release` 워크플로우
- 태그 릴리즈와 자산 업로드

최신 변경 이력은 [CHANGELOG.md](./CHANGELOG.md)에서 관리한다.
