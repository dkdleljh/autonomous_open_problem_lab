# 프로그램 상세 설계서

## 1. 설계 목표

Autonomous Open Problem Lab의 설계 목표는 세 가지다.

1. 난제 후보 수집부터 릴리즈 산출물 생성까지를 하나의 자동 파이프라인으로 묶는다.
2. 중간 산출물과 의사결정을 모두 추적 가능하고 검증 가능한 구조로 남긴다.
3. 운영 준비도가 부족한 상태에서는 실제로 자동화가 멈추도록 한다.

이 프로젝트는 단순한 "스크립트 모음"이 아니라, 상태 머신, 게이트 정책, 산출물 schema, 감사 로그, 릴리즈 자동화가 한 흐름으로 연결된 시스템으로 설계되어 있다.

## 2. 최상위 구성

### 2.1 애플리케이션 레이어

- `aopl/apps/harvester.py`
- `aopl/apps/registry.py`
- `aopl/apps/normalizer.py`
- `aopl/apps/scorer.py`
- `aopl/apps/counterexample_engine.py`
- `aopl/apps/proof_engine.py`
- `aopl/apps/verifier.py`
- `aopl/apps/formalizer.py`
- `aopl/apps/paper_generator.py`
- `aopl/apps/submission_builder.py`
- `aopl/apps/orchestrator.py`

### 2.2 코어 레이어

- `aopl/core/types.py`: 데이터 클래스와 직렬화
- `aopl/core/state_machine.py`: 단계 전이 규칙
- `aopl/core/gates.py`: 게이트 판정 정책
- `aopl/core/schema_utils.py`: 런타임 schema 검증
- `aopl/core/config_store.py`: 중앙 설정 로더
- `aopl/core/io_utils.py`: JSON/YAML/Text 입출력

### 2.3 서비스 레이어

- `aopl/services/engine_factory.py`: demo/real 백엔드 선택

### 2.4 외부 운영 레이어

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `scripts/release/create_release.py`
- `scripts/release/auto_update.py`

## 3. 파이프라인 개요

전체 파이프라인은 아래 순서를 따른다.

1. Harvester가 문제 후보를 수집한다.
2. Registry가 canonical problem record를 만든다.
3. Normalizer가 구조화된 문제 표현을 만든다.
4. Scorer가 점수와 선택 여부를 계산한다.
5. Counterexample engine이 강한형을 점검한다.
6. Proof engine이 proof DAG를 만든다.
7. Verifier가 중대 이슈와 경고를 판정한다.
8. Formalizer가 Lean skeleton과 build report를 만든다.
9. Paper generator가 한영 논문과 appendix, PDF를 만든다.
10. Submission builder가 bundle과 checksum을 만든다.
11. Orchestrator가 상태 전이, 감사 로그, run summary를 기록한다.

## 4. 상태 머신 설계

### 4.1 상태 목록

- `REGISTERED`
- `HARVESTED`
- `NORMALIZED`
- `SCORED`
- `SELECTED`
- `COUNTEREXAMPLE_CHECKED`
- `LEMMA_GRAPH_BUILT`
- `DRAFT_PROOF_CREATED`
- `INTERNAL_VERIFICATION_PASSED`
- `FORMALIZATION_ATTEMPTED`
- `PAPER_DRAFT_GENERATED`
- `PAPER_QA_PASSED`
- `SUBMISSION_PACKAGE_READY`
- `RELEASED`
- `BLOCKED`

### 4.2 전이 규칙

- 모든 전이는 상태 머신을 통해서만 이뤄진다.
- 임의 상태 점프는 허용하지 않는다.
- 각 단계는 성공 여부와 실패 사유를 명시적으로 남긴다.
- 실패 시 바로 `BLOCKED`로 전이할 수 있다.

## 5. 게이트 설계

### 5.1 GatePolicy

`aopl/core/gates.py`는 게이트 정책을 오케스트레이터 밖으로 분리한다. 이 구조 덕분에 정책 변경이 구현 변경과 섞이지 않는다.

### 5.2 대표 게이트

- Harvest Gate
- Normalize Gate
- Counterexample Gate
- Proof Integrity Gate
- Verification Gate
- Formalization Gate
- Paper QA Gate
- Release Gate

### 5.3 Release Gate 특징

기본 정책에서는 다음 조건을 엄격히 본다.

- verification pass
- formal build success
- pdf build success
- checksum 존재
- submission package 존재
- demo artifact 허용 여부

## 6. demo / real 백엔드 분리

현재 프로젝트는 일부 모듈에서 `demo`와 `real` 백엔드를 분리해 둔다.

- `counterexample_backend`
- `proof_backend`
- `formalizer_backend`
- `paper_generator_backend`

선택은 `runtime.yaml`과 `EngineFactory`를 통해 이뤄진다.

이 설계는 두 가지 목적을 가진다.

1. 데모 흐름과 실제 연구용 흐름을 명시적으로 구분한다.
2. 동일한 타입 계약을 유지하면서 구현을 교체한다.

## 7. 데이터 계약과 schema enforcement

주요 JSON 산출물은 생성 시점과 읽기 시점 모두에서 검증된다.

### 7.1 검증 대상

- problem registry
- status history
- normalized problem
- score card
- counterexample report
- proof DAG
- verification report
- verification log entry
- formalization report
- paper manifest
- submission manifest
- stage event
- run summary

### 7.2 효과

- 깨진 파일을 늦게 읽고 터지는 문제를 줄인다.
- 테스트에서 산출물 구조를 명시적으로 보장한다.
- downstream 모듈이 입력 형식을 신뢰할 수 있다.

## 8. provenance 설계

수집 provenance는 파이프라인 전반에 걸쳐 전달된다.

대표 필드:

- `harvest_batch_id`
- `harvest_entry_index`
- `source_hashes`
- `source_signature`
- `candidate_hash`

이 정보는 registry, audit log, run summary, submission manifest까지 이어진다.

## 9. 감사 로그 설계

### 9.1 pipeline audit

- 위치: `data/audit_logs/pipeline_audit.jsonl`
- 역할: 단계별 event 기록

### 9.2 verification log

- 위치: `data/audit_logs/verification_log.jsonl`
- 역할: verifier 단위 로그

### 9.3 last run summary

- 위치: `data/audit_logs/last_run_summary.json`
- 역할: 한 번 실행한 결과를 사람이 빠르게 읽도록 요약

이 세 로그는 서로 다른 관점을 가진다. audit는 이벤트 스트림, verification log는 검증 중심 스트림, run summary는 최종 스냅샷이다.

## 10. 형식화와 논문 설계

### 10.1 형식화

- proof DAG를 Lean skeleton으로 변환
- import 자동 생성
- obligation 집계
- build 시도 여부와 성공 여부 분리
- `artifact_kind`로 placeholder와 build artifact를 구분

### 10.2 논문 생성

- 공통 semantic graph 생성
- 한국어/영어 LaTeX 초안 생성
- appendix 생성
- QA 검사
- PDF build 시도
- `pdf_artifact_kind`로 placeholder와 actual build를 구분

## 11. 운영 준비도 100점 설계

### 11.1 정의

이 프로젝트에서 100점은 "운영 준비도"다. 추상적 완벽함이 아니다.

### 11.2 구현

- `aopl doctor`
- `quality_policy.yaml`
- `--strict`
- GitHub CI와 Release의 doctor gate
- 로컬 자동 업데이트와 릴리즈 스크립트의 doctor gate

### 11.3 프로필

- `local`
- `ci`
- `github_release`

각 프로필은 필수 체크 이름과 최소 점수를 가진다.

## 12. GitHub 릴리즈 설계

### 12.1 create_release.py

- doctor strict
- pytest
- run-all
- 버전 계산
- 태그 생성
- push
- GitHub Release 생성

### 12.2 release workflow

- doctor strict
- pytest
- 샘플 파이프라인
- 릴리즈 노트 생성
- `gh release edit`
- `gh release upload --clobber`

### 12.3 이유

GitHub Release 자산 업로드를 `gh` CLI 기반으로 유지하면 액션 런타임 의존성을 줄이고 경고를 줄일 수 있다.

## 13. 제한 사항

- 수학적 정당성 자체를 완전 판정하는 엔진은 아니다.
- 형식화와 논문화는 아직 강한 template 성격이 남아 있다.
- real backend는 최소 유효 구현 수준이며, 연구 엔진으로는 추가 고도화가 필요하다.
- 모든 오픈 문제를 자동 수집·해결하는 범용 엔진은 아니다.

## 14. 향후 확장 포인트

1. 실제 외부 문제 수집 커넥터 확장
2. 더 강한 finite search / SAT / SMT 반례 엔진
3. proof planning 고도화
4. Lean build 성공률 향상
5. 저널별 논문 템플릿 세분화
6. 운영 대시보드 및 메트릭 수집
