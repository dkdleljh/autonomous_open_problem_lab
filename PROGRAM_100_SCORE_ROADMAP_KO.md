# 100점 프로그램 로드맵

## 1. 목표 재정의

이 프로젝트의 현실적인 목표는 다음과 같다.

- 모든 수학 난제를 푸는 범용 해결기가 아니라
- 연구 파이프라인을 끝까지 무인 오케스트레이션하는 시스템

이 정의 아래에서 100점은 "주장한 범위 안에서 결함이 거의 없는 상태"를 뜻한다.

## 2. 즉시 보강 가능한 항목

### 2.1 수집 계층

- 실제 커넥터 추가
  - arXiv
  - OEIS 관련 문제군
  - 위키 기반 오픈 문제 목록
  - 수동 YAML 입력 커넥터
- source dedup rule 고도화
- source reliability calibration 추가

### 2.2 반례 엔진

- finite brute force backend 확장
- SAT/SMT backend 연결
- domain-specific graph search backend 추가
- 탐색 spec schema 추가

### 2.3 증명 엔진

- counterexample-guided proof planning 강화
- proof template보다 rule-based planner 중심으로 이동
- domain별 planner 분리

### 2.4 형식화

- Lean 프로젝트 빌드 단위 테스트
- theorem 이름과 declaration mapping 강화
- obligation dependency 추적 추가

### 2.5 논문화

- 저널 프로파일 추가
- citation style 자동 선택
- section completeness score 추가
- abstract, limitations, reproducibility의 정량 QA 강화

### 2.6 운영 자동화

- release preflight script
- docs freshness check
- manifest diff checker
- artifact retention policy

## 3. 즉시 100점이 불가능한 항목

다음 항목은 코드 보강만으로 해결되지 않는다.

1. 모든 수학 난제 자동 해결
2. 인간 수학자 수준의 완벽한 증명 창출
3. 저널 심사 기준에서 완벽한 논문 자동 작성

## 4. 현실적 목표 점수표

- 무인 자동화 파이프라인: 100점 가능
- 추적성, 감사, 스키마 일관성: 100점 가능
- 문서, 운영, 릴리즈 자동화: 100점 가능
- 범용 난제 해결 능력: 100점 불가능
- 범용 완벽 논문 작성: 100점 불가능
