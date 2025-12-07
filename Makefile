.PHONY: help install install-dev test test-cov lint format type-check clean build publish

help:
	@echo Available commands:
	@echo   install       - Install package dependencies
	@echo   install-dev   - Install package with dev dependencies
	@echo   test          - Run tests
	@echo   test-cov      - Run tests with coverage report
	@echo   lint          - Run linters (ruff)
	@echo   format        - Format code with black
	@echo   type-check    - Run type checker (mypy)
	@echo   clean         - Remove build artifacts
	@echo   build         - Build package
	@echo   publish       - Publish to PyPI
	@echo   publish-test  - Publish to TestPyPI

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

test:
	pytest tests/

test-cov:
	pytest --cov=drone_mobile --cov-report=html --cov-report=term-missing tests/

lint:
	ruff check drone_mobile/

format:
	black drone_mobile/ tests/
	ruff check --fix drone_mobile/

type-check:
	mypy drone_mobile/

clean:
	python -c "import shutil; import os; [shutil.rmtree(p, ignore_errors=True) for p in ['build', 'dist', 'htmlcov', '.pytest_cache', 'drone_mobile.egg-info']]"
	python -c "import os; [os.remove(f) for f in ['.coverage'] if os.path.exists(f)]"
	python -c "import pathlib; [p.unlink() for p in pathlib.Path('.').rglob('*.py[co]') if p.is_file()]"
	python -c "import shutil; import pathlib; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__') if p.is_dir()]"

build: clean
	python -m build

publish: build
	twine upload dist/*

publish-test: build
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*
