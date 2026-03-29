# Proof Engine 앱

`aopl/apps/proof_engine.py`는 선택된 문제에 대해 증명 전략의 뼈대를 DAG 형태로 만드는 단계다.

## 역할

- lemma, dependency, subgoal 관계를 그래프로 정리한다.
- demo 또는 real 백엔드를 통해 proof 후보 구조를 생성한다.
- verifier와 formalizer가 읽을 중간 산출물을 만든다.

## 주요 출력

- `data/proof_dag/*_proof_dag.json`
- proof outline, 의존 관계, 미해결 노드 정보

## 운영 팁

- proof DAG는 완성된 증명이 아니라 검증 가능한 구조 초안이다.
- node를 너무 크게 만들면 verifier와 formalizer 단계가 동시에 어려워진다.
