# Normalizer 앱

`aopl/apps/normalizer.py`는 자유형 텍스트와 수집 메타데이터를 구조화된 문제 표현으로 바꾸는 단계다.

## 역할

- 객체, 가정, 목표를 구조화한다.
- 동치형, 약화형, 강화형 후보를 정리한다.
- normalized schema에 맞는지 검증한다.

## 주요 출력

- `data/normalized/*_normalized.json`
- 후속 점수 계산과 proof 단계가 읽을 공통 형식 데이터

## 운영 팁

- normalizer 출력 품질이 낮으면 scorer, verifier, paper 단계까지 전부 품질이 흔들린다.
- 용어 표기가 흔들리면 `docs/style_guides/terminology.md` 기준으로 다시 맞추는 것이 좋다.
