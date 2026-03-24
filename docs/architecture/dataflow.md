# 데이터 흐름 문서

## 1. 입력 흐름

1. `data/raw_sources/sample_open_problems.json` 또는 외부 소스 커넥터 입력
2. harvester가 수집 스냅샷 생성
3. registry가 canonical 문제 레코드 생성

입력 단계 산출물:

- `data/raw_sources/latest_harvest.json`
- `data/registry/problem_registry.json`
- `data/registry/status_history.json`

## 2. 처리 흐름

### 2.1 정규화

normalizer는 문제 진술을 객체, 가정, 목표로 분해하고 동치형, 약화형, 강화형 후보를 생성한다.

산출물:

- `data/normalized/<problem_id>_normalized.json`

### 2.2 점수화

scorer는 다음 지표를 계산한다.

- 형식화 가능성
- 분해 가능성
- 라이브러리 적합도
- 반례 탐색 가능성
- 논문화 용이성

산출물:

- `data/normalized/<problem_id>_score.json`

### 2.3 반례 탐색

counterexample_engine은 강한형부터 탐색한다. 반례가 발견되면 약화형 권고를 생성하고 로그에 범위와 seed를 저장한다.

산출물:

- `data/experiments/<problem_id>_counterexample.json`

### 2.4 증명 탐색

proof_engine은 보조정리 후보, 환원 경로, 주정리 초안을 DAG로 저장한다.

산출물:

- `data/proof_dag/<problem_id>_proof_dag.json`
- `data/proof_dag/failure_memory.json`

### 2.5 검증

verifier는 금지 표현, DAG 단절, 문헌 중복, 강한형 붕괴 후 처리 여부를 판정한다.

산출물:

- `data/theorem_store/<problem_id>_verification.json`
- `data/audit_logs/verification_log.jsonl`

## 3. 형식화 흐름

1. proof DAG를 Lean skeleton으로 변환
2. import 자동 구성
3. obligation 목록 생성
4. Lean 빌드 시도

산출물:

- `formal/generated_skeletons/<problem_id>.lean`
- `formal/proof_obligations/<problem_id>_formalization_report.json`
- `formal/proof_obligations/<problem_id>_lean_build.log`

## 4. 논문화 흐름

1. 공통 의미 그래프 생성
2. 한국어, 영어 LaTeX 동시 생성
3. BibTeX 생성
4. 재현성 부록 생성
5. 논문 QA 실행

산출물:

- `papers/shared/<problem_id>_semantic_graph.json`
- `papers/ko/<problem_id>.tex`
- `papers/en/<problem_id>.tex`
- `papers/shared/<problem_id>.bib`
- `papers/shared/<problem_id>_appendix.md`
- `papers/builds/<problem_id>.pdf`

## 5. 제출 흐름

submission_builder는 논문 및 부속 파일을 묶어 제출 패키지와 체크섬을 생성한다.

산출물:

- `data/paper_assets/releases/<problem_id>_<timestamp>.zip`
- `data/paper_assets/releases/<problem_id>_<timestamp>_source.tar.gz`
- `data/paper_assets/releases/<problem_id>_<timestamp>_checksums.txt`
- `data/paper_assets/releases/<problem_id>_<timestamp>_release_notes.md`
- `data/paper_assets/releases/<problem_id>_<timestamp>_submission_manifest.json`

## 6. 감사 로그 흐름

모든 게이트 판정은 `data/audit_logs/pipeline_audit.jsonl`에 저장되며 마지막 실행 요약은 `data/audit_logs/last_run_summary.json`으로 기록된다. 차단 사유 집계와 failure class 요약은 `data/audit_logs/last_incident_summary.json`에 별도로 남는다. 최근 `doctor` 실행 결과와 정책 lint 스냅샷은 `data/audit_logs/last_doctor_report.json`에 저장되며, 이후 release note와 submission manifest가 이를 재사용한다.
