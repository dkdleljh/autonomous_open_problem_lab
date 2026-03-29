# Graph Store 서비스

proof DAG와 관련 그래프 데이터를 저장하고 재사용하는 서비스 레이어다.

## 역할

- lemma 관계와 dependency edge를 구조화해 보존한다.
- proof 단계와 verifier 단계 사이의 데이터 전달 안정성을 높인다.

## 운영 팁

- 그래프 노드 식별 규칙이 흔들리면 diff와 재현성이 급격히 나빠진다.
