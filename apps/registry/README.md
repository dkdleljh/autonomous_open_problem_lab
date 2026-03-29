# Registry 앱

`aopl/apps/registry.py`는 수집된 후보를 프로젝트의 표준 문제 레코드로 등록하는 관문이다.

## 역할

- 문제 식별자와 canonical record를 생성한다.
- 상태 이력 파일을 갱신해 단계 전이를 추적 가능하게 만든다.
- registry 관련 JSON schema를 검증한다.

## 주요 입력

- harvester 단계 산출물
- 기존 `data/registry/problem_registry.json`
- 상태 이력 파일

## 주요 출력

- 최신 problem registry
- status history
- registry merge 결과 로그

## 운영 팁

- 동일 문제가 여러 소스에서 들어오면 merge 기준을 먼저 확인해야 한다.
- registry가 깨지면 downstream 단계가 연쇄 실패하므로, 수동 수정 후에는 schema 검증을 다시 돌리는 편이 안전하다.
