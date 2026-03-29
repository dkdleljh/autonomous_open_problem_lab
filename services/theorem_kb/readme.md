# Theorem KB 서비스

정리 단위 산출물과 검증 결과를 저장하는 지식 베이스 계층이다.

## 역할

- theorem 메타데이터와 verification 결과를 연결한다.
- 재사용 가능한 theorem 기록을 구조화해 보존한다.

## 운영 팁

- theorem 레벨 메타데이터는 논문 생성보다 verifier와 release gate에서 더 자주 참조된다.
- 현재는 `data/theorem_store`를 기본 저장소로 사용하며, 필요 시 외부 DB로 치환할 수 있다.
