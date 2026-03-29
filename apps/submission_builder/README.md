# Submission Builder 앱

`aopl/apps/submission_builder.py`는 외부 제출이나 공개 배포에 필요한 최종 패키지를 조립하는 단계다.

## 역할

- 제출 번들 zip, tar.gz, checksum을 생성한다.
- 포함 파일과 검증 요약을 담은 manifest를 만든다.
- 릴리즈 노트와 연결될 메타데이터를 정리한다.

## 주요 출력

- `data/paper_assets/releases/`
- `submission_manifest.json`
- checksum 파일

## 운영 팁

- bundle이 생성됐다고 바로 배포 가능한 것은 아니다.
- release gate가 차단한 상태라면 패키지가 있어도 공개 배포를 진행하지 않는 것이 맞다.
