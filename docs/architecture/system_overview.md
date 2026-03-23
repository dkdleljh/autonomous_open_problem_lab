# 시스템 전체 구조

## 1. 목적

Autonomous Open Problem Lab은 난제 수집부터 제출 패키지 생성까지 전 과정을 자동화하는 연구 자동화 시스템이다. 시스템의 핵심 목표는 결과 주장 자체가 아니라, 근거 기반 탐색과 검증 가능 산출물을 안정적으로 생산하는 것이다.

## 2. 계층 구조

시스템은 다음 계층으로 구성된다.

1. 오케스트레이션 계층
   - `aopl/apps/orchestrator.py`
   - 상태 머신 전이, 품질 게이트 판정, 작업 순서 제어

2. 도메인 처리 계층
   - `harvester`, `registry`, `normalizer`, `scorer`, `counterexample_engine`, `proof_engine`, `verifier`, `formalizer`, `paper_generator`, `submission_builder`
   - 각 모듈은 입력과 출력이 명확하며 독립 실행 가능하다.

3. 데이터 및 아티팩트 계층
   - `data/` 하위 경로에 수집, 정규화, proof DAG, 실험 로그, 감사 로그를 저장
   - `papers/` 하위 경로에 한영 논문 초안 및 빌드 결과 저장
   - `formal/` 하위 경로에 Lean skeleton과 obligation 보고 저장

4. 자동화 및 배포 계층
   - `scripts/release/*.py`
   - `.github/workflows/*.yml`
   - 자동 커밋, 태그, 릴리즈 노트, 아티팩트 게시 흐름 지원

## 3. 핵심 설계 원칙

### 3.1 완전 무인 실행

수동 승인 단계 없이 게이트 규칙으로만 전이를 허용한다. 실패 시 자동 차단하고 감사 로그에 근거를 남긴다.

### 3.2 반례 탐색과 증명 탐색 분리

강한형 명제의 붕괴 여부를 먼저 점검하고, 붕괴 시 약화형으로 자동 이관한다. 반례 결과를 증명 성공으로 오인하지 않도록 파이프라인을 분리했다.

### 3.3 proof DAG 중심 추적

모든 증명 탐색은 DAG 구조로 저장한다. 이는 논리 단절 검증, 형식화 브리지 생성, 논문 서술 연결의 공통 기반이 된다.

### 3.4 계산 실험의 역할 제한

계산 결과는 실험적 지지로만 기록한다. 일반 명제 해결 주장에 직접 사용하지 않으며, 탐색 범위, seed, 시간, 제약을 항상 저장한다.

### 3.5 형식화 가시성

형식화 실패 또는 미해결 obligation은 보고서에 명시한다. 미완료 상태를 숨기지 않는다.

### 3.6 양언어 번호 동기화

공통 의미 그래프를 먼저 만들고 한국어, 영어 논문을 동시에 생성하여 정리 번호, 수식 번호, 참고문헌 번호를 일치시킨다.

## 4. 모듈 책임 요약

- `orchestrator`: 상태 머신과 품질 게이트의 단일 진입점
- `harvester`: 수집, 스냅샷, 중복 제거
- `registry`: canonical 문제 기록과 상태 이력
- `normalizer`: 문제 구조화 JSON 생성
- `scorer`: 다중 기준 점수 산출
- `counterexample_engine`: 유한 범위 반례 탐색
- `proof_engine`: 보조정리 후보와 proof DAG 구축
- `verifier`: 논리 공백, 가정 누수, 문헌 충돌 검사
- `formalizer`: Lean skeleton 생성과 obligation 추적
- `paper_generator`: 한영 논문 초안과 부록 생성
- `submission_builder`: 제출 번들, 체크섬, 매니페스트 생성

## 5. 확장성 포인트

- 저장소 계층: SQLite에서 PostgreSQL 또는 외부 graph DB로 확장 가능
- 반례 엔진: Rust 크레이트를 확장해 고성능 탐색 전략 추가 가능
- 형식화 계층: Lean 외 타 검증기 브리지 추가 가능
- 논문화 계층: 저널 프로파일 및 템플릿 다중화 가능
