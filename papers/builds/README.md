# papers/builds

논문 빌드 산출물을 저장하는 디렉터리다.

## 포함 내용

- PDF 파일
- paper manifest JSON
- 빌드 로그 또는 placeholder 결과

## 운영 팁

- PDF가 존재해도 manifest의 `pdf_artifact_kind`가 placeholder인지 actual인지 함께 확인해야 한다.
