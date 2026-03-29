# proof_obligations

형식화 단계에서 생성된 의무 사항과 unresolved 항목을 저장하는 디렉터리다.

## 포함 내용

- formalization report JSON
- unresolved obligation 목록
- build 성공 여부와 실패 이유

## 해석 포인트

- unresolved가 남아 있어도 skeleton 생성은 성공할 수 있다.
- 따라서 "파일이 만들어졌다"와 "형식 검증이 끝났다"를 같은 뜻으로 보면 안 된다.
