# Formalizer 앱

`aopl/apps/formalizer.py`는 proof DAG를 Lean 중심의 형식화 시도 산출물로 바꾸는 단계다.

## 역할

- Lean skeleton 파일을 생성한다.
- unresolved obligation과 build 결과를 정리한다.
- placeholder 아티팩트와 실제 build 산출물을 구분한다.

## 주요 출력

- `formal/generated_skeletons/`
- `formal/proof_obligations/*_formalization_report.json`

## 운영 팁

- skeleton 생성 성공과 formal build 성공은 다른 상태다.
- unresolved obligation이 길어질수록 논문 생성 전에 proof 구조 재검토가 필요하다.
