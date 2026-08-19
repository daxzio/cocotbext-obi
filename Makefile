.PHONY: help clean dist lint mypy format checks pre-commit release \
	test test_all test_icarus test_verilator git_align

help:
	@echo "cocotbext-obi Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  test       - Run all tests (SIMS=icarus verilator; or SIM=icarus)"
	@echo "  lint       - Run pyflakes and ruff linters"
	@echo "  mypy       - Run mypy type checker"
	@echo "  format     - Format code with black"
	@echo "  checks     - Run format, lint and mypy"
	@echo "  pre-commit - Run all pre-commit hooks"
	@echo "  dist       - Build distribution packages"
	@echo "  release    - Tag and publish a release (make release GIT_TAG=x.y.z)"
	@echo "  clean      - Clean build artifacts"
	@echo "  install    - Install package in development mode"

SIMS?=icarus verilator

# CI uses `make test SIM=icarus`. Honor a command-line SIM as the simulator list.
ifeq ($(origin SIM),command line)
SIMS := $(SIM)
endif

test:
	@echo "Running all tests on simulators: $(SIMS)"
	$(MAKE) test_all SIMS="$(SIMS)"

test_all:
	@for sim in $(SIMS); do \
		echo "\n=== Running tests with $$sim ==="; \
		(cd tests/test_basic && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_basic_64 && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_slverr && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_device && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_ram && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_memdump && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_pipelining && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_addrmap && $(MAKE) clean sim SIM=$$sim REGWIDTH=8 WAVES=0) || exit $$?; \
		(cd tests/test_addrmap && $(MAKE) clean sim SIM=$$sim REGWIDTH=16 WAVES=0) || exit $$?; \
		(cd tests/test_addrmap && $(MAKE) clean sim SIM=$$sim REGWIDTH=32 WAVES=0) || exit $$?; \
		(cd tests/test_poll && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_early_external_read && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_interface && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
		(cd tests/test_interface_noid && $(MAKE) clean sim SIM=$$sim WAVES=0) || exit $$?; \
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
	mypy cocotbext/obi

format:
	black cocotbext tests scripts

checks: format lint mypy

pre-commit:
	pre-commit run --all-files

dist:
	@echo "Building distribution packages..."
	python -m build
	@echo "Checking package..."
	twine check dist/*

GIT_TAG?=1.0.0
VERSION_FILE?=`find cocotbext -name version.py`
release:
	echo "Release v${GIT_TAG}"
	git tag v${GIT_TAG} || { echo "make release GIT_TAG=0.0.5"; git tag ; exit 1; }
	echo "__version__ = \"${GIT_TAG}\"" > ${VERSION_FILE}
	git add ${VERSION_FILE}
	git commit --allow-empty -m "Update to version ${GIT_TAG}"
	git tag -f v${GIT_TAG}
	git push && git push --tags

git_align:
	mkdir -p repos
	cd repos ; git clone git@github.com:daxzio/rtlflo.git 2> /dev/null || (cd rtlflo ; git pull)
	rsync -artu --exclude .git repos/rtlflo/ tests/rtlflo
	rsync -artu --exclude .git tests/rtlflo/ repos/rtlflo

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
