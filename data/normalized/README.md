# data/normalized

정규화 결과와 점수 계산 결과가 함께 쌓이는 디렉터리다.

## 포함 내용

- `*_normalized.json`
- `*_score.json`

## 용도

- proof, verifier, paper 단계의 공통 입력
- 선별 근거와 문제 표현 일관성 확보

## 운영 팁

- 사람이 직접 수정하기보다 upstream normalizer 설정을 고쳐 재생성하는 편이 안전하다.
