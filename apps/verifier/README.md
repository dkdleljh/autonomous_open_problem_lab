# Verifier 앱

`aopl/apps/verifier.py`는 proof DAG와 각종 산출물을 읽고 다음 단계로 넘어가도 되는지 판정하는 검증 단계다.

## 역할

- critical issue, warning, gate reason을 계산한다.
- 논리 공백, 가정 누수, 참고문헌 충돌, 금지 표현을 검사한다.
- verification report와 verification log를 남긴다.

## 주요 출력

- `data/theorem_store/*_verification.json`
- `data/audit_logs/verification_log.jsonl`

## 운영 팁

- warning이 많다고 항상 차단되지는 않지만 release 단계에서 운영 위험으로 승격될 수 있다.
- verifier가 차단한 이유는 대부분 이전 단계 설계 문제와 연결되어 있다.
