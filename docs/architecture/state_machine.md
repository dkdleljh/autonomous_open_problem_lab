# 상태 머신 정의

## 1. 상태 목록

1. REGISTERED
2. HARVESTED
3. NORMALIZED
4. SCORED
5. SELECTED
6. COUNTEREXAMPLE_CHECKED
7. LEMMA_GRAPH_BUILT
8. DRAFT_PROOF_CREATED
9. INTERNAL_VERIFICATION_PASSED
10. FORMALIZATION_ATTEMPTED
11. PAPER_DRAFT_GENERATED
12. PAPER_QA_PASSED
13. SUBMISSION_PACKAGE_READY
14. RELEASED
15. BLOCKED

## 2. 전이 조건

상태 전이는 항상 게이트 판정 결과에 의해 결정된다.

- 게이트 통과: 다음 상태로 전이
- 게이트 실패: BLOCKED로 전이

`aopl/core/state_machine.py`의 `StageMachine.transition`이 단일 전이 규칙을 강제한다.

## 3. 단계별 게이트 대응

- REGISTERED -> HARVESTED: Harvest Gate
- HARVESTED -> NORMALIZED: Normalize Gate
- NORMALIZED -> SCORED: Score Gate
- SCORED -> SELECTED: Selection Gate
- SELECTED -> COUNTEREXAMPLE_CHECKED: Counterexample Gate
- COUNTEREXAMPLE_CHECKED -> LEMMA_GRAPH_BUILT: Proof Integrity Gate
- LEMMA_GRAPH_BUILT -> DRAFT_PROOF_CREATED: Draft Gate
- DRAFT_PROOF_CREATED -> INTERNAL_VERIFICATION_PASSED: Verification Gate
- INTERNAL_VERIFICATION_PASSED -> FORMALIZATION_ATTEMPTED: Formalization Gate
- FORMALIZATION_ATTEMPTED -> PAPER_DRAFT_GENERATED: Paper Draft Gate
- PAPER_DRAFT_GENERATED -> PAPER_QA_PASSED: Paper QA Gate
- PAPER_QA_PASSED -> SUBMISSION_PACKAGE_READY: Submission Gate
- SUBMISSION_PACKAGE_READY -> RELEASED: Release Gate

## 4. 실패 처리 정책

게이트 실패 시 정책은 다음과 같다.

1. 즉시 BLOCKED 상태로 전이
2. 실패 사유와 메타데이터를 감사 로그에 저장
3. 상태 이력 파일에 전이 기록
4. 같은 실행에서 해당 문제의 후속 단계 중단

## 5. 자동 재시도 기준

재시도는 설정 파일 `configs/global/runtime.yaml`의 `max_retry_per_stage`를 따른다. 단, 다음 조건은 재시도 없이 즉시 차단한다.

- 중대한 논리 공백
- 참고문헌 충돌 미해결
- 형식화 붕괴 임계값 초과
- 강한형 반례 발견 후 약화형 권고 부재
