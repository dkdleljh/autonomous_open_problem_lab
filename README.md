# Autonomous Open Problem Lab

완전 무인 방식으로 수학 난제 후보를 수집하고, 정규화, 우선순위화, 반례 탐색, 증명 탐색, 검증, 형식화 시도, 한영 논문 초안 생성, 제출 패키지 생성을 자동 수행하는 통합 시스템이다.

## 왜 이 시스템이 필요한가

수학 난제 연구 자동화는 단순 계산 자동화와 다르다. 문제 선정 기준, 반례와 증명의 분리, 논리 공백 검출, 형식화 가능성 점검, 논문 번호 동기화, 재현성 아티팩트 관리가 동시에 필요하다. 이 프로젝트는 연구 파이프라인 전체를 하나의 상태 머신으로 묶어, 사람이 매단계 승인하지 않아도 품질 게이트를 통해 자동 차단과 자동 이관을 수행한다.

## 무엇을 자동화하는가

- 난제 후보 자동 수집과 중복 제거
- canonical 문제 레지스트리 구축
- 정규화 JSON 생성과 동치형, 약화형, 강화형 관리
- 점수 기반 우선순위화
- 강한형 반례 탐색과 약화형 자동 전환
- proof DAG 구축과 실패 경로 기록
- 검증 게이트 기반 자동 차단
- Lean 4 skeleton 생성과 obligation 보고
- 한국어, 영어 논문 초안 동시 생성
- 제출 패키지, 체크섬, 릴리즈 노트 생성

## 무엇을 보장하지 않는가

- 실제 미해결 난제를 반드시 해결한다고 보장하지 않는다.
- 계산 실험 결과만으로 일반 명제를 해결했다고 주장하지 않는다.
- 형식화가 완료되지 않은 구간을 숨기지 않는다.

## 바탕화면 저장 정책

프로젝트 루트는 `autonomous_open_problem_lab`로 통일한다. 운영체제별 바탕화면 감지는 `aopl/core/paths.py`에서 처리하며, 기본 규칙은 다음과 같다.

- Windows: `%USERPROFILE%/Desktop` 또는 `OneDrive/Desktop`
- macOS, Linux: `~/Desktop`
- 바탕화면 미존재 시 홈 디렉터리로 폴백

## 설치 방법

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .[dev]
```

## 빠른 시작

```bash
.venv/bin/aopl run-all --root . --limit 1
```

단계별 실행 예시는 다음과 같다.

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

## 주요 모듈 설명

- `aopl/apps/harvester.py`: 수집, 스냅샷, 중복 제거
- `aopl/apps/registry.py`: canonical record, alias, 상태 이력
- `aopl/apps/normalizer.py`: 객체, 가정, 목표 분리와 정규화
- `aopl/apps/scorer.py`: 점수 계산과 선택
- `aopl/apps/counterexample_engine.py`: 강한형 반례 탐색
- `aopl/apps/proof_engine.py`: proof DAG 생성
- `aopl/apps/verifier.py`: 논리 공백, 문헌 충돌, 금지 표현 검사
- `aopl/apps/formalizer.py`: Lean skeleton 생성과 보고서
- `aopl/apps/paper_generator.py`: 한영 논문 동시 생성
- `aopl/apps/submission_builder.py`: 제출 패키지와 체크섬 생성
- `aopl/apps/orchestrator.py`: 전체 상태 머신과 게이트 제어

## 완전 무인 자동화 흐름

`REGISTERED → HARVESTED → NORMALIZED → SCORED → SELECTED → COUNTEREXAMPLE_CHECKED → LEMMA_GRAPH_BUILT → DRAFT_PROOF_CREATED → INTERNAL_VERIFICATION_PASSED → FORMALIZATION_ATTEMPTED → PAPER_DRAFT_GENERATED → PAPER_QA_PASSED → SUBMISSION_PACKAGE_READY → RELEASED`

각 단계는 게이트 통과 여부로만 전이하며 수동 승인 단계를 두지 않는다.

## 품질 게이트

- Harvest Gate: 출처 신뢰도 임계값 검사
- Normalize Gate: 정의, 가정, 목표 분리 검사
- Counterexample Gate: 강한형 붕괴 시 약화형 권고 검사
- Proof Integrity Gate: DAG 순환, 단절 검사
- Verification Gate: 중대 논리 이슈, 금지 표현 검사
- Formalization Gate: 미해결 obligation 임계값 검사
- Paper QA Gate: 번호 동기화, 참고문헌, 부록 검사
- Release Gate: 패키지, 체크섬, 노트 존재 검사

## 출력물 예시

- `data/audit_logs/last_run_summary.json`
- `data/proof_dag/*_proof_dag.json`
- `formal/generated_skeletons/*.lean`
- `papers/ko/*.tex`
- `papers/en/*.tex`
- `papers/builds/*.pdf`
- `data/paper_assets/releases/*.zip`

## 논문 생성 구조

공통 의미 그래프를 `papers/shared/*_semantic_graph.json`으로 먼저 생성하고, 그 그래프를 입력으로 한국어, 영어 LaTeX를 생성한다. 정리 번호와 수식 번호는 공통 그래프를 기준으로 동기화된다.

## 릴리즈 자동화 구조

- CI: `.github/workflows/ci.yml`
- Release: `.github/workflows/release.yml`
- 로컬 자동 릴리즈: `scripts/release/create_release.py`
- 자동 업데이트: `scripts/release/auto_update.py`

`create_release.py`는 테스트, 파이프라인 실행, 버전 계산, 태그 생성, 릴리즈 노트 생성을 자동화한다. 원격 인증이 없는 경우 로컬 태그와 노트만 생성하고 안내 메시지를 출력한다.

## GitHub 연동

1. 원격 저장소 연결

```bash
git remote add origin <YOUR_REPOSITORY_URL>
```

2. 인증 정보 설정

- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY` 예: `owner/repo`

3. main 브랜치 push

```bash
git push -u origin main
```

4. 태그 릴리즈

```bash
python3 scripts/release/create_release.py --mode github --bump patch
```

## 프로젝트 제한 사항

- 기본 데이터 저장소는 SQLite 또는 JSON 파일 기반 시작 구성이며 대규모 분산 환경은 후속 확장 대상이다.
- Lean 전체 프로젝트 빌드는 로컬 Lean 설치 여부에 따라 자동 시도 후 결과를 보고서에 기록한다.

## 향후 개선 방향

- Neo4j 기반 proof graph 저장 확장
- SAT, SMT 기반 반례 탐색 플러그인 추가
- 다중 형식검증기 연동
- 원격 계산 노드 스케줄러 확장
- 저널별 제출 규격 프로파일 추가
