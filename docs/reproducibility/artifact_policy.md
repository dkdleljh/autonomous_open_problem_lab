# 아티팩트 정책

## 1. 필수 아티팩트

- normalized JSON
- score JSON
- counterexample report
- proof DAG
- verification report
- formalization report
- ko/en 논문 원본
- BibTeX
- 부록
- 제출 패키지
- 체크섬

## 2. 저장 규칙

모든 아티팩트는 프로젝트 루트 내부에만 저장한다.

- 중간 산출물: `data/`
- 형식화 산출물: `formal/`
- 논문 산출물: `papers/`
- 릴리즈 산출물: `data/paper_assets/releases/`

## 3. 무결성 검증

제출 패키지 생성 시 모든 파일 해시를 계산해 체크섬 파일을 생성한다.

## 4. 보존 정책

- 감사 로그: 최소 365일 보존
- 릴리즈 아티팩트: 삭제 전 체크섬 백업 필수
