# 기여 가이드

## 1. 기본 원칙

이 프로젝트는 기능 추가보다 운영 가능성, 추적성, 재현성을 우선한다. 즉, "돌아간다"만으로는 충분하지 않다. 다음 조건이 동시에 맞아야 한다.

- 타입과 데이터 계약이 유지됨
- schema 검증이 깨지지 않음
- doctor strict가 의도대로 작동함
- 테스트와 Ruff가 통과함
- 문서가 변경 사항을 반영함

## 2. 브랜치 전략

- 기본 브랜치: `main`
- 기능 브랜치 예시: `feature/<topic>`
- 수정 브랜치 예시: `fix/<topic>`
- 문서 브랜치 예시: `docs/<topic>`
- 운영 브랜치 예시: `ci/<topic>`, `release/<topic>`

## 3. 커밋 메시지 규칙

권장 접두사:

- `feat:`
- `fix:`
- `docs:`
- `test:`
- `refactor:`
- `ci:`
- `release:`
- `chore:`

좋은 메시지 예시:

- `feat: enforce strict doctor quality gates`
- `ci: provision workflow quality dependencies`
- `docs: expand user guide for release operations`

피해야 할 메시지:

- `update`
- `fix bug`
- `misc`

## 4. 코드 수정 전 체크

수정 전에 아래를 먼저 확인한다.

1. 변경 대상 모듈의 README 또는 설계 문서가 있는가
2. 산출물 schema가 영향을 받는가
3. Orchestrator, doctor, workflow에 연결 영향이 있는가
4. 테스트 추가가 필요한가
5. 문서 업데이트가 필요한가

## 5. 코드 품질 규칙

- 타입 힌트 유지
- 예외 메시지는 명확하게 작성
- 실패 사유를 숨기지 않음
- placeholder artifact를 실제 결과처럼 표현하지 않음
- provenance 필드를 제거하거나 약화하지 않음
- 무인 운영을 깨는 수동 승인 단계를 몰래 넣지 않음

## 6. 문서 품질 규칙

- 기본 문서는 한국어로 작성
- 현실과 다른 과장은 금지
- 시스템 한계와 실패 조건을 분명히 적음
- 사용자가 바로 실행할 수 있는 명령 예시를 넣음
- 문서 간 역할이 겹치면 README는 개요, GUIDE는 절차, DESIGN은 구조 중심으로 나눈다

## 7. 테스트 규칙

최소 기준:

- `pytest -q`
- `ruff check aopl tests scripts`

변경 종류별 권장 테스트:

- schema 변경: 관련 runtime/schema 테스트
- gate 변경: gate policy 테스트
- output 변경: regression 테스트
- CLI 변경: parser/output 테스트
- workflow 변경: 최소한 로컬 doctor 및 관련 스크립트 확인

## 8. 권장 로컬 검증 순서

```bash
.venv/bin/aopl doctor --root . --profile local --strict
.venv/bin/ruff check aopl tests scripts
.venv/bin/pytest -q
.venv/bin/aopl run-all --root . --limit 1
```

릴리즈 관련 변경이면 추가로 아래를 확인한다.

```bash
.venv/bin/aopl doctor --root . --profile github_release --strict
python3 scripts/release/create_release.py --mode local --bump patch --python .venv/bin/python
```

## 9. Pull Request 체크리스트

- [ ] `doctor --profile local --strict` 통과
- [ ] `ruff check aopl tests scripts` 통과
- [ ] `pytest -q` 통과
- [ ] 필요한 문서 업데이트 완료
- [ ] schema 변경 시 관련 테스트 보강 완료
- [ ] 산출물 이름, 경로, manifest 영향도 검토 완료
- [ ] 릴리즈 또는 CI 변경 시 workflow 영향도 검토 완료

## 10. 금지 사항

- failing test를 삭제만 해서 통과시키기
- placeholder artifact를 actual build처럼 표기하기
- verification critical issue를 무시하고 통과 처리하기
- release gate를 임시로 약화한 뒤 되돌리지 않기
- 사용 문서 갱신 없이 인터페이스 바꾸기

## 11. 문서 책임 분담

- `README.md`: 진입 문서
- `PROGRAM_USER_GUIDE.md`: 설치, 실행, 운영 절차
- `PROGRAM_DETAILED_DESIGN.md`: 구조와 설계
- `CHANGELOG.md`: 변경 이력
- `docs/`: 세부 아키텍처와 운영 지침

기여자는 변경 내용이 이 분담과 어긋나지 않는지 확인해야 한다.
