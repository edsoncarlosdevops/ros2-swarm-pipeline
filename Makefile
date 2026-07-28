.PHONY: help lint install-python build-cpp etl etl-generate analyze validate docker-build docker-up docker-down test all clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================
# Code Quality
# ============================================================
lint: ## Run flake8 on all Python code
	flake8 ros2_nodes/ etl_pipeline/ --max-line-length=100

# ============================================================
# ROS 2 Nodes
# ============================================================
install-python: ## Install Python ROS 2 package (drone_telemetry)
	cd ros2_nodes/drone_telemetry && pip install -e .

build-cpp: ## Build C++ ROS 2 package with colcon
	cd ros2_nodes/drone_bridge && colcon build --symlink-install

# ============================================================
# ETL Pipeline
# ============================================================
etl-generate: ## Generate synthetic MCAP data (500 messages)
	python etl_pipeline/mcap_to_parquet.py --generate-mcap --count=500

etl: ## Run full ETL pipeline (MCAP → Parquet)
	python etl_pipeline/mcap_to_parquet.py

analyze: ## Run DuckDB analytical queries on Parquet
	python etl_pipeline/analyze_flight.py

validate: ## Validate Parquet and analytics thresholds
	python etl_pipeline/validate_parquet.py
	python etl_pipeline/validate_analytics.py

# ============================================================
# Docker
# ============================================================
docker-build: ## Build all Docker images (multi-arch)
	docker compose build

docker-up: ## Start all ROS 2 nodes via Docker Compose
	docker compose up -d

docker-down: ## Stop all Docker Compose services
	docker compose down

docker-logs: ## Tail logs from all containers
	docker compose logs -f

# ============================================================
# Testing & CI
# ============================================================
test: lint validate ## Run lint + validation (CI-ready)

ci: test etl analyze ## Full CI pipeline (lint → ETL → analytics)

# ============================================================
# Utilities
# ============================================================
clean: ## Remove generated artifacts
	rm -rf data/raw/*.mcap data/processed/*.parquet data/processed/metadata.json
	rm -rf ros2_nodes/drone_bridge/build/ ros2_nodes/drone_bridge/install/ ros2_nodes/drone_bridge/log/
	rm -rf __pycache__/ .pytest_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

all: lint etl-generate etl analyze validate ## Run everything (lint + ETL + analyze + validate)