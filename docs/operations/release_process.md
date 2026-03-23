# 릴리즈 프로세스

## 1. 로컬 릴리즈 흐름

1. 테스트 실행
2. 무인 파이프라인 실행
3. 변경사항 스테이징
4. 커밋 생성
5. 버전 계산
6. 태그 생성
7. 릴리즈 노트 생성

명령:

```bash
python3 scripts/release/create_release.py --mode local --bump patch
```

## 2. GitHub 릴리즈 흐름

1. `main`에 변경 반영
2. 태그 push
3. `release.yml` 자동 실행
4. 테스트, 문서 검증, 패키지 빌드
5. 릴리즈 노트 자동 생성
6. GitHub Release 생성과 아티팩트 첨부

## 3. 커밋 메시지 규칙

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `test: ...`
- `release: vX.Y.Z 자동 릴리즈 준비`

## 4. main 푸시 규칙

기본 브랜치는 `main`이며, CI 통과를 기본 조건으로 한다.

```bash
git push origin main
```

## 5. 태그 생성 규칙

Semantic Versioning 사용:

- `v0.1.0`
- `v0.1.1`
- `v0.2.0`

## 6. 릴리즈 노트 생성

스크립트:

```bash
python3 scripts/release/generate_release_notes.py --tag v0.1.0
```

Release 워크플로우는 해당 파일을 본문으로 사용한다.

## 7. 아티팩트 첨부 항목

- 제출 패키지 zip
- 소스 번들 tar.gz
- 체크섬 파일
- 논문 PDF
- paper manifest

## 8. 인증 정보 정책

- `GITHUB_TOKEN`과 `GITHUB_REPOSITORY`를 환경변수로 사용
- 민감정보는 코드에 하드코딩하지 않는다.
- 인증 미설정 시 스크립트는 명확한 오류 메시지와 함께 중단한다.
