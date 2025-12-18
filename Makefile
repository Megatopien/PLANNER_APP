.PHONY: help lint test run docker-run

help:
	@echo "Available commands:"
	@echo "  make help         Show this help"
	@echo "  make lint         Run code linting"
	@echo "  make test         Run tests"
	@echo "  make run          Run the API locally"
	@echo "  make docker-run   Run the project with Docker"

lint:
	python3 -m flake8 api || true

test:
	pytest

run:
	python3 -m uvicorn api.app:app --reload

docker-run:
	docker compose up --build

docker-down:
	docker compose down -v


