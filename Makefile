.PHONY: help clean dist lint mypy test

help:
	@echo "cocotbext-obi Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  test       - Run all tests"
	@echo "  lint       - Run flake8 linter"
	@echo "  mypy       - Run mypy type checker"
	@echo "  dist       - Build distribution packages"
	@echo "  clean      - Clean build artifacts"
	@echo "  install    - Install package in development mode"

test:
	@echo "Running tests in tests/test_slverr..."
	cd tests/test_slverr && make etana && make sim SIM=verilator

lint:
	@echo "Running flake8..."
	flake8 cocotbext/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 cocotbext/ --count --max-complexity=10 --max-line-length=119 --statistics

mypy:
	@echo "Running mypy..."
	mypy cocotbext/obi --ignore-missing-imports || true

dist:
	@echo "Building distribution packages..."
	python -m build
	@echo "Checking package..."
	twine check dist/*

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf cocotbext_obi.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name sim_build -exec rm -rf {} + 2>/dev/null || true
	find . -name results.xml -delete
	find . -name "*.vcd" -delete
	find . -name "*.fst" -delete

install:
	@echo "Installing in development mode..."
	pip install -e .

.DEFAULT_GOAL := help

