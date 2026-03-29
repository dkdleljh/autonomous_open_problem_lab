# data/audit_logs

이 디렉터리는 파이프라인 실행 중 발생한 이벤트와 운영 판단 근거를 저장한다.

## 대표 파일

- `pipeline_audit.jsonl`: 단계별 이벤트 스트림
- `verification_log.jsonl`: verifier 중심 검증 로그
- `last_run_summary.json`: 가장 최근 실행의 최종 요약
- `last_incident_summary.json`: 최근 차단, 예외, failure class 요약
- `last_doctor_report.json`: 최근 doctor 실행 결과와 정책 lint 결과

## 읽는 방법

- 상세 타임라인이 필요하면 `jsonl`
- 운영 상태를 빨리 보고 싶으면 `last_*` 스냅샷 파일

## 운영 팁

- 릴리즈 실패 원인을 찾을 때는 `last_incident_summary.json`과 `last_doctor_report.json`을 같이 보는 편이 가장 빠르다.
