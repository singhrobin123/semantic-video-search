.PHONY: help install dev test lint db up down seed ingest-demo clean

# ── Default ─────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ───────────────────────────────────────────────────────────────
install: ## Install Python dependencies
	cd backend && pip install -r requirements.txt

dev: ## Start backend + frontend for local development
	@echo "Starting pgvector..."
	docker-compose up -d pgvector
	@echo "Waiting for DB to be healthy..."
	@sleep 3
	@echo "Starting backend (port 8000)..."
	cd backend && uvicorn app.main:app --reload --port 8000 &
	@echo "Starting frontend (port 8501)..."
	cd frontend && streamlit run app.py --server.port 8501 &

# ── Database ────────────────────────────────────────────────────────────
db: ## Start only the pgvector database
	docker-compose up -d pgvector

seed: ## Seed the database with demo transcript data
	cd backend && python -m app.db.seed

# ── Docker ──────────────────────────────────────────────────────────────
up: ## Start all services via Docker Compose
	docker-compose up -d --build

down: ## Stop all services
	docker-compose down

clean: ## Stop services and remove volumes
	docker-compose down -v

# ── Testing ─────────────────────────────────────────────────────────────
test: ## Run the full test suite
	cd backend && python -m pytest tests/ -v --tb=short

test-unit: ## Run only unit tests
	cd backend && python -m pytest tests/unit/ -v --tb=short

test-integration: ## Run only integration tests
	cd backend && python -m pytest tests/integration/ -v --tb=short

test-cov: ## Run tests with coverage report
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

# ── Utilities ───────────────────────────────────────────────────────────
lint: ## Run type checking and linting
	cd backend && python -m mypy app/ --ignore-missing-imports
