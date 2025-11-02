.PHONY: help install setup verify test clean

help:
	@echo "Texas Hold'em MCCFR System - Available Commands"
	@echo "================================================"
	@echo ""
	@echo "Setup commands:"
	@echo "  make install     - Install dependencies and package"
	@echo "  make setup       - Run setup script (create directories)"
	@echo "  make verify      - Verify installation"
	@echo ""
	@echo "Development commands:"
	@echo "  make test        - Run test suite"
	@echo "  make clean       - Clean generated files"
	@echo ""
	@echo "CLI wrapper scripts (in bin/):"
	@echo "  ./bin/holdem-build-buckets     - Build abstraction buckets"
	@echo "  ./bin/holdem-train-blueprint   - Train MCCFR strategy"
	@echo "  ./bin/holdem-eval-blueprint    - Evaluate strategy"
	@echo "  ./bin/holdem-profile-wizard    - Calibrate table"
	@echo "  ./bin/holdem-dry-run           - Test in observation mode"
	@echo "  ./bin/holdem-autoplay          - Run auto-play mode"
	@echo ""
	@echo "For more information, see README.md"

install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt || echo "Some dependencies may have failed to install"
	@echo "Installing package in editable mode..."
	pip install -e . || echo "Package install failed - you can still use wrapper scripts in bin/"
	@make setup
	@make verify

setup:
	@echo "Running setup script..."
	python3 setup.py

verify:
	@echo "Verifying installation..."
	python3 test_structure.py

test:
	@echo "Running test suite..."
	pytest tests/ -v

clean:
	@echo "Cleaning generated files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf build/ dist/ .coverage htmlcov/
	@echo "Clean complete!"
