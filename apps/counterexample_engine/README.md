# Counterexample Engine 앱

`aopl/apps/counterexample_engine.py`는 현재 가정이 너무 강하거나 잘못된 경우를 빠르게 드러내기 위한 반례 탐색 단계다.

## 역할

- demo 또는 real 백엔드를 선택해 반례 탐색을 수행한다.
- 탐색 범위, seed, 실패 사유, 약화형 권고를 기록한다.
- 위배 사례가 발견되면 이후 단계를 차단할 근거를 남긴다.

## 주요 출력

- `data/experiments/*_counterexample.json`
- audit 로그용 탐색 요약

## 운영 팁

- 반례가 없다는 결과는 정답 보장이 아니라, 현재 탐색 범위에서 실패하지 않았다는 뜻이다.
- seed와 탐색 범위를 함께 기록해야 나중에 같은 결과를 재현할 수 있다.
