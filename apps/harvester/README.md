# Harvester 앱

`aopl/apps/harvester.py`는 외부 문제 후보를 내부 파이프라인이 처리할 수 있는 초기 입력으로 정리하는 수집 단계다.

## 역할

- 외부 소스에서 문제 후보를 수집한다.
- 수집 시점, 원본 위치, 해시 등 provenance 정보를 함께 남긴다.
- 중복 후보를 정리하고 registry 단계가 읽을 수 있는 형태로 정리한다.

## 주요 입력

- `configs/problems/` 아래의 문제 소스 설정
- `data/raw_sources/`에 저장되는 원본 스냅샷

## 주요 출력

- 수집 스냅샷
- provenance 메타데이터
- registry 단계로 전달할 canonical candidate 목록

## 운영 팁

- 수집 결과가 기대보다 적으면 파서 설정, 원본 소스 접근성, 해시 충돌 여부를 먼저 확인한다.
- provenance가 비어 있으면 이후 audit 추적성이 약해지므로, 편의상 필드를 줄이지 않는 편이 좋다.
