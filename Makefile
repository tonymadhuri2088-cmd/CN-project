# Developer shortcuts. Run `make help`.
.PHONY: help install test lint typecheck cov reproduce ui check
help:
	@echo "install | test | lint | typecheck | cov | reproduce | ui | check (everything CI runs)"
install:
	pip install -e ".[dev,lint,typecheck]"
test:
	python -m pytest -q
lint:
	ruff check netwing tests
typecheck:
	mypy
cov:
	python -m pytest -q --cov=netwing --cov-branch --cov-report=term-missing
reproduce:
	python -m netwing.reproduce check --strict
ui:
	netwing-ui --results results
check: lint typecheck test reproduce
