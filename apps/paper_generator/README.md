# Paper Generator 앱

`aopl/apps/paper_generator.py`는 검증된 산출물을 한글/영문 논문 초안과 appendix로 바꾸는 단계다.

## 역할

- 공통 semantic graph를 바탕으로 ko/en 초안을 생성한다.
- appendix와 manifest를 함께 만든다.
- PDF 빌드 성공 여부와 placeholder 여부를 구분해 기록한다.

## 주요 출력

- `papers/ko/`, `papers/en/`
- `papers/shared/`
- `papers/builds/*_paper_manifest.json`

## 운영 팁

- 초안 생성 성공이 곧 학술 품질 보장을 의미하지는 않는다.
- 문단 번호, 참고문헌, appendix 연결 상태는 QA 단계에서 다시 확인하는 편이 좋다.
