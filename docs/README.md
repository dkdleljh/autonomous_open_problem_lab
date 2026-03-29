# 문서 인덱스

이 디렉터리는 `Autonomous Open Problem Lab`의 세부 운영 문서를 주제별로 나눈 공간이다. 처음 읽는 사람은 전체 구조를 잡고, 운영자는 필요한 섹션만 빠르게 찾을 수 있도록 구성했다.

## 권장 읽기 순서

1. [`../README.md`](../README.md)
2. [`../PROGRAM_USER_GUIDE.md`](../PROGRAM_USER_GUIDE.md)
3. [`../PROGRAM_DETAILED_DESIGN.md`](../PROGRAM_DETAILED_DESIGN.md)
4. [`operations/runbook.md`](operations/runbook.md)
5. [`architecture/system_overview.md`](architecture/system_overview.md)

## 문서 묶음 설명

- `architecture/`: 시스템 구조, 데이터 흐름, 상태 머신, 품질 게이트, 자율 운영 정책
- `operations/`: 일상 운영, 릴리즈, 롤백, 장애 대응
- `reproducibility/`: 실험 재현성과 산출물 관리 기준
- `style_guides/`: 코드, 논문, 용어 작성 규칙

## 읽는 사람별 추천 경로

- 처음 설치하는 사람: `README.md` → `PROGRAM_USER_GUIDE.md`
- 구조를 이해하려는 사람: `PROGRAM_DETAILED_DESIGN.md` → `architecture/`
- 운영 담당자: `operations/`
- 논문/산출물 품질을 관리하는 사람: `reproducibility/`와 `style_guides/`

## 문서 관리 원칙

- 루트 문서는 전체 개요와 진입 흐름을 맡는다.
- `docs/` 아래 문서는 세부 정책과 운영 절차를 맡는다.
- 하위 디렉터리 `README.md`는 해당 폴더의 역할과 대표 파일을 빠르게 설명한다.

## 4. 재현성 문서

- `reproducibility/artifact_policy.md`
- `reproducibility/experiment_policy.md`
- `reproducibility/seed_policy.md`
- `reproducibility/citation_policy.md`

이 묶음은 산출물과 실험 정책을 다룬다.

## 5. 스타일 가이드

- `style_guides/code_style.md`
- `style_guides/paper_style.md`
- `style_guides/terminology.md`

이 묶음은 코드, 논문, 용어 사용 기준을 다룬다.

## 6. 관련 루트 문서

- `../PROGRAM_REALITY_CHECK_KO.md`: 현재 시스템의 현실 점검
- `../PROGRAM_100_SCORE_ROADMAP_KO.md`: 운영 준비도와 고도화 로드맵

## 7. 문서 관리 원칙

- README는 진입 문서
- USER GUIDE는 실행 절차
- DETAILED DESIGN은 구조 설명
- CONTRIBUTING은 협업 규칙
- CHANGELOG는 사용자 관점 변경 이력
- `docs/`는 하위 세부 지침
