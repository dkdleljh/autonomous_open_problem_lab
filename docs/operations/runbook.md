# 운영 런북

## 1. 설치 후 전체 실행 절차

1. 가상환경 생성

```bash
python3 -m venv .venv
```

2. 의존성 설치

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .[dev]
```

3. 기본 점검

```bash
.venv/bin/pytest -q
```

4. 전체 파이프라인 실행

```bash
.venv/bin/aopl run-all --root . --limit 2
```

## 2. 단계별 수동 실행

```bash
.venv/bin/aopl harvest --root .
.venv/bin/aopl normalize --root .
.venv/bin/aopl score --root .
.venv/bin/aopl counterexample --root .
.venv/bin/aopl proof --root .
.venv/bin/aopl verify --root .
.venv/bin/aopl formalize --root .
.venv/bin/aopl paper --root .
.venv/bin/aopl submission --root .
```

## 3. 스케줄링 운영

권장 스케줄:

- 일일 수집: 새벽 2시
- 주간 재구축: 월요일 새벽 3시 30분
- 출판 런: 토요일 새벽 5시

스케줄 자동화는 OS 스케줄러 또는 GitHub Actions cron으로 구성한다.

## 4. 초기 부트스트랩

```bash
python3 scripts/bootstrap/init_on_desktop.py
```

위 명령은 운영체제별 바탕화면 경로를 감지하여 프로젝트 루트를 준비한다.

## 5. 로그 확인 방법

- 파이프라인 이벤트: `data/audit_logs/pipeline_audit.jsonl`
- 검증 로그: `data/audit_logs/verification_log.jsonl`
- 실행 요약: `data/audit_logs/last_run_summary.json`

## 6. 장기 운영 방법

1. 주기 실행 스크립트 사용

```bash
python3 scripts/maintenance/run_unattended_cycle.py --limit 2
```

2. 자동 업데이트 반영

```bash
python3 scripts/release/auto_update.py --push
```

3. 릴리즈 생성

```bash
python3 scripts/release/create_release.py --mode local --bump patch
```
