PYTHON ?= python3
VENV ?= .venv

.PHONY: help venv install lint test run-all harvest normalize score counterexample proof verify formalize paper submission package clean

help:
	@printf "사용 가능한 명령:\n"
	@printf "  make venv        - 가상환경 생성\n"
	@printf "  make install     - 의존성 설치\n"
	@printf "  make lint        - 정적 검사\n"
	@printf "  make test        - 테스트 실행\n"
	@printf "  make run-all     - 전체 무인 파이프라인 실행\n"
	@printf "  make release-local - 로컬 릴리즈 준비\n"

venv:
	$(PYTHON) -m venv $(VENV)

install:
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -e .[dev]

lint:
	$(VENV)/bin/ruff check aopl tests scripts

test:
	$(VENV)/bin/pytest -q

harvest:
	$(VENV)/bin/aopl harvest

normalize:
	$(VENV)/bin/aopl normalize

score:
	$(VENV)/bin/aopl score

counterexample:
	$(VENV)/bin/aopl counterexample

proof:
	$(VENV)/bin/aopl proof

verify:
	$(VENV)/bin/aopl verify

formalize:
	$(VENV)/bin/aopl formalize

paper:
	$(VENV)/bin/aopl paper

submission:
	$(VENV)/bin/aopl submission

run-all:
	$(VENV)/bin/aopl run-all

package:
	$(VENV)/bin/aopl submission

release-local:
	$(VENV)/bin/python scripts/release/create_release.py --mode local

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
