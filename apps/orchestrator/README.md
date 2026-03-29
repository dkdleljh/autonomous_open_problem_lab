# Orchestrator 앱

`aopl/apps/orchestrator.py`는 전체 상태 머신을 제어하는 중심 엔트리다.

## 역할

- 단계 실행 순서를 제어한다.
- 각 단계 성공 여부와 게이트 결과를 기록한다.
- audit event, run summary, incident summary를 갱신한다.
- 실패 시 `BLOCKED` 전이와 차단 사유 기록을 담당한다.

## 주요 출력

- `data/audit_logs/pipeline_audit.jsonl`
- `data/audit_logs/last_run_summary.json`
- `data/audit_logs/last_incident_summary.json`

## 운영 팁

- 무인 운영 품질은 orchestrator의 차단 정책에 크게 좌우된다.
- 실패를 억지로 숨기기보다 차단 사유를 데이터로 남기는 현재 설계를 유지하는 편이 장기적으로 안전하다.
