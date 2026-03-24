# 변경 이력

이 문서는 사용자가 "최근 무엇이 달라졌는지"를 빠르게 확인할 수 있도록 유지한다. 상세 구현 이유는 커밋과 설계 문서를 참고하고, 여기서는 사용자 영향과 운영 영향 중심으로 기록한다.

## v0.1.4

- GitHub Release 워크플로우에서 `softprops/action-gh-release`를 제거하고 `gh` CLI 기반 자산 업로드로 전환
- Release 워크플로우의 Node 20 deprecation 경고 제거
- `release.yml`이 릴리즈 노트 갱신과 자산 업로드를 명시적으로 수행하도록 단순화

## v0.1.3

- GitHub Actions 공식 액션 버전을 최신 계열로 상향
- `actions/checkout`, `actions/setup-python`, `actions/upload-artifact` 버전 정리
- CI 워크플로우의 Node 20 deprecation 경고 제거

## v0.1.2

- GitHub Actions 러너에 Lean/Lake, LaTeX 설치 단계를 추가
- `doctor --strict`, `pytest`, 샘플 파이프라인, 릴리즈 자산 업로드까지 GitHub Actions에서 실제 성공
- `v0.1.2` 릴리즈 아티팩트 업로드 검증 완료

## v0.1.1

- `doctor`에 GitHub 인증 fallback 추가
- `gh auth token`과 `origin` 원격 URL을 통해 `GITHUB_TOKEN`, `GITHUB_REPOSITORY` 대체 판정 지원
- LaTeX 설치 후 `github_release` 프로필 100점 달성

## v0.1.0

- 연구 파이프라인 자동화 저장소 초기 릴리즈
- 수집, 정규화, 점수화, 반례 점검, proof DAG, 검증, 형식화, 논문 초안, 제출 패키지 흐름 제공

## 최근 구조 개선 요약

아래 항목은 단일 버전에 묶기보다 최근 여러 커밋에 걸쳐 강화된 내용이다.

- demo/real 백엔드 분리
- gate 로직 분리
- registry merge/idempotent 처리
- provenance 필드 확장
- schema enforcement 확대
- doctor strict 정책 도입
- GitHub CI / Release 자동화 강화

## 최근 운영 안정성 강화

- 경로 탈출, 심볼릭 링크 우회, LaTeX/Lean 문자열 주입, 외부 툴 무기한 대기 문제를 차단하는 보강 적용
- 런타임 예외를 문제 단위로 격리하고 retry/backoff, transient/permanent 분류, lookback 기반 승격 정책 도입
- `last_incident_summary.json`, `last_doctor_report.json`을 표준 운영 산출물로 추가하고 `doctor`, release note, submission manifest, CI artifact, GitHub release asset이 이를 공통 소비
- GitHub Release 워크플로우와 로컬 `create_release.py`가 운영 위험 감지 시 기본 차단하고, 수동 override에서만 완화되도록 통일
- `auto_update.py`, `create_release.py`, `generate_release_notes.py`의 공통 운영 위험 판정 로직을 `scripts/release/release_common.py`로 정리
