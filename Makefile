.PHONY: install dev clean lint test run worker docker-build docker-up docker-down

# 安装依赖
install:
	uv sync

# 安装开发依赖
dev:
	uv sync --extra dev

# 清理项目
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache

# 代码检查
lint:
	uv run ruff check .
	uv run black --check .
	uv run isort --check .

# 格式化代码
format:
	uv run ruff check --fix .
	uv run black .
	uv run isort .

# 运行测试
test:
	uv run pytest -v

# 运行 Web 服务
run:
	uv run uvicorn pulse_guard.main:app --host 0.0.0.0 --port 8000 --reload

# 运行 Celery Worker
worker:
	uv run celery -A pulse_guard.worker.celery_app worker --loglevel=info

# Docker 相关命令
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
