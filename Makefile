.PHONY: help clean dist lint mypy test test_all test_icarus test_verilator

help:
	@echo "cocotbext-obi Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  test       - Run all tests"
	@echo "  lint       - Run pyflakes and ruff linters"
	@echo "  mypy       - Run mypy type checker"
	@echo "  dist       - Build distribution packages"
	@echo "  clean      - Clean build artifacts"
	@echo "  install    - Install package in development mode"

SIMS?=icarus verilator

test:
	@echo "Running all tests on default simulators: $(SIMS)"
	$(MAKE) test_all SIMS="$(SIMS)"

test_all:
	@for sim in $(SIMS); do \
		echo "\n=== Running tests with $$sim ==="; \
		(cd tests/test_basic && $(MAKE) clean etana sim SIM=$$sim) || exit $$?; \
		(cd tests/test_basic_64 && $(MAKE) clean etana sim SIM=$$sim) || exit $$?; \
		(cd tests/test_slverr && $(MAKE) clean etana sim SIM=$$sim) || exit $$?; \
	done

test_icarus:
	$(MAKE) test_all SIMS="icarus"

test_verilator:
	$(MAKE) test_all SIMS="verilator"

lint:
	@echo "Running pyflakes..."
	pyflakes cocotbext/
	@echo "Running ruff..."
	ruff check cocotbext/

mypy:
	@echo "Running mypy type checker..."
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

