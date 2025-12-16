# Makefile for tg-wp-bridge

.PHONY: help install test tests test-coverage test-html lint format typecheck run clean docker-build docker-run docker-stop build ci

# Default target
help:
	@echo "Available targets:"
	@echo "  install          Install dependencies with uv"
	@echo "  test             Run all tests"
	@echo "  tests            Alias for test"
	@echo "  test-coverage    Run tests with coverage report"
	@echo "  test-html        Run tests with HTML coverage report"
	@echo "  build            Build the project package"
	@echo "  lint             Run linting with ruff"
	@echo "  lintfix             Run linting with ruff"
	@echo "  format           Format code with ruff"
	@echo "  typecheck        Run type checking with mypy"
	@echo "  check            Run all checks (lint, format, typecheck)"
	@echo "  run              Run the development server"
	@echo "  clean            Clean cache and temporary files"
	@echo "  docker-build     Build Docker image"
	@echo "  docker-run       Run with Docker Compose"
	@echo "  docker-stop      Stop Docker Compose services"
	@echo "  ci               Run full CI pipeline"

# Development setup
install:
	uv sync --dev

# Testing
test:
	uv run pytest -v

tests: test

test-coverage:
	uv run pytest --cov=tg_wp_bridge --cov-report=term-missing --cov-report=html --cov-report=xml --cov-branch

test-html:
	uv run pytest --cov=tg_wp_bridge --cov-report=html && open htmlcov/index.html

# Build
build:
	uv build

# Code quality
lint:
	uv run ruff check tg_wp_bridge tests

lintfix:
	uv run ruff check tg_wp_bridge tests --fix

format:
	uv run ruff format tg_wp_bridge tests

typecheck:
	uv run mypy tg_wp_bridge

check: lint typecheck

# Running
run:
	uv run uvicorn tg_wp_bridge.app:app --reload

# Cleaning
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov .mypy_cache dist build

# Docker
docker-build:
	docker build -f docker/Dockerfile -t tg-wp-bridge .

docker-run:
	cd docker && docker-compose up -d

docker-stop:
	cd docker && docker-compose down

# CI pipeline
ci: install test-coverage lint format typecheck
	@echo "All CI checks passed!"
