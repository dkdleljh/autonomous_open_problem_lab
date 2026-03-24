# 장애 대응 정책

## 1. 장애 분류

### P1

- 데이터 손상
- 릴리즈 패키지 생성 실패
- 검증 게이트 허위 통과 의심

### P2

- 특정 단계 반복 실패
- 형식화 빌드 실패 증가
- 논문 QA 반복 실패

### P3

- 경고 수준 참고문헌 중복
- 선택 점수 임계값 미세 조정 필요

## 2. 자동 차단 규칙

다음은 즉시 차단한다.

- 논리 공백 critical
- 강한형 반례 발견 후 약화형 권고 없음
- 참고문헌 누락
- 재현성 부록 누락
- Release 아티팩트 누락

## 3. 자동 격리 규칙

- 특정 문제만 실패한 경우 해당 문제만 BLOCKED 처리
- 나머지 문제는 계속 실행
- 격리된 문제는 `status_history.json`에 사유 저장

## 4. 자동 복구 규칙

- 비중대 오류는 최대 2회 재시도
- 재시도 간 대기 시간은 `configs/global/queue.yaml`의 `retry_policy.backoff_seconds`
- `transient` 실패만 재시도
- `permanent` 실패는 재시도 없이 즉시 BLOCKED
- 재시도 실패 시 BLOCKED
- 다음 실행 주기에 동일 문제를 재평가

## 5. 장애 확인 파일

- `data/audit_logs/pipeline_audit.jsonl`: 단계별 이벤트와 retry 이벤트
- `data/audit_logs/last_doctor_report.json`: 최근 doctor strict 결과와 정책 lint 스냅샷
- `data/audit_logs/last_run_summary.json`: 최근 실행 전체 요약
- `data/audit_logs/last_incident_summary.json`: failure class 요약과 주요 차단 사유
- `aopl doctor --strict`: 운영 필수 체크와 정책 lint 결과

## 6. 제한적 수동 개입 절차

수동 개입은 아래 경우에만 허용한다.

1. 저장소 손상 복구
2. 잘못된 환경변수 수정
3. 외부 서비스 장애로 인한 연결 실패 복구

수동 개입 후에는 반드시 다음 절차를 다시 수행한다.

1. `pytest -q`
2. `aopl doctor --root . --profile local --strict`
3. `aopl run-all --limit 1`
4. 감사 로그 확인
