# 품질 게이트 정의

## 1. Harvest Gate

- 목적: 출처 신뢰도 미달 데이터 차단
- 입력: source 목록과 reliability
- 통과 조건: 평균 신뢰도 >= `harvest_min_reliability`
- 실패 조건: 출처 없음 또는 평균 신뢰도 부족

## 2. Normalize Gate

- 목적: 정의, 가정, 목표 분리 실패 차단
- 입력: normalized JSON
- 통과 조건: objects, assumptions, target 모두 비어 있지 않음
- 실패 조건: 세 구성 요소 중 하나라도 누락

## 3. Score Gate

- 목적: 자동 공략 대상 선별
- 입력: ScoreCard
- 통과 조건: `selection.min_score` 이상
- 실패 조건: 임계값 미달

## 4. Counterexample Gate

- 목적: 강한형 붕괴 탐지와 안전 이관
- 입력: counterexample report
- 통과 조건:
  - 반례 미발견 또는
  - 반례 발견 시 약화형 권고 존재
- 실패 조건: 반례 발견 + 약화형 권고 없음

## 5. Proof Integrity Gate

- 목적: proof DAG 구조 무결성 검증
- 입력: proof DAG JSON
- 통과 조건: DAG 무순환, 루트에서 목표까지 경로 존재
- 실패 조건: 순환 또는 단절

## 6. Verification Gate

- 목적: 논리 공백, 가정 누수, 문헌 충돌 차단
- 입력: verifier report
- 통과 조건: critical issue 0건
- 실패 조건: critical issue 1건 이상

## 7. Formalization Gate

- 목적: 형식화 붕괴 방지
- 입력: formalization report
- 통과 조건: unresolved obligation <= 임계값
- 실패 조건: 임계값 초과

## 8. Paper QA Gate

- 목적: 논문 일관성 보장
- 입력: paper manifest, ko/en tex
- 통과 조건:
  - 번호 동기화 유지
  - 참고문헌 누락 없음
  - 부록 파일 존재
- 실패 조건: 하나라도 위반

## 9. Release Gate

- 목적: 배포 산출물 완결성 보장
- 입력: submission manifest
- 통과 조건:
  - package, source bundle, checksum, release notes 존재
- 실패 조건: 필수 산출물 누락

## 10. 예외 없는 실패 규칙

아래 항목은 자동 실패로 취급하며 수동 우회를 허용하지 않는다.

- 계산 결과만으로 일반 명제 해결 주장
- 금지 표현 사용
- 참고문헌 누락
- 재현성 부록 누락
- 반례 탐색 범위, seed, 시간 미기록
- proof DAG 없이 논문 생성 시도
- 한영 정리 또는 수식 번호 불일치
- 형식화 실패 상태 은닉
