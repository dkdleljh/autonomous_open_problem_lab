# 롤백 절차

## 1. 롤백 대상

- 잘못된 릴리즈 태그
- 품질 게이트 누락 상태로 생성된 패키지
- 잘못된 릴리즈 노트

## 2. 로컬 롤백

1. 잘못된 태그 삭제

```bash
git tag -d <TAG>
```

2. 릴리즈 산출물 정리

```bash
rm -f data/paper_assets/releases/*<TAG>*
```

3. 재검증 후 새 태그 생성

```bash
python3 scripts/release/create_release.py --mode local --bump patch
```

## 3. 원격 롤백

1. 원격 태그 삭제

```bash
git push origin :refs/tags/<TAG>
```

2. 잘못된 GitHub Release 삭제

```bash
gh release delete <TAG> --yes
```

3. 수정 반영 후 새 태그 배포

```bash
python3 scripts/release/create_release.py --mode github --bump patch
```

## 4. 브랜치 정리

- 기본 브랜치는 `main`
- 롤백은 태그와 릴리즈 단위로 수행하고, 히스토리 파괴 명령은 사용하지 않는다.

## 5. 사후 점검

- `data/audit_logs/last_run_summary.json` 확인
- `papers/builds/*.pdf` 최신 생성 여부 확인
- 체크섬 파일 유효성 재검증
