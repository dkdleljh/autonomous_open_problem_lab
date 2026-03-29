# data/registry

프로젝트가 현재 알고 있는 문제 목록과 단계 이력을 저장하는 핵심 디렉터리다.

## 대표 파일

- `problem_registry.json`
- `status_history.json`

## 역할

- 현재 어떤 문제가 어느 단계에 있는지 보여 준다.
- 상태 머신 전이의 감사 추적 기반이 된다.

## 운영 팁

- registry가 깨지면 파이프라인 전체가 흔들린다. 수동 수정 후에는 schema 검증과 doctor를 함께 돌리는 편이 좋다.
