#!/bin/bash

# 简单的启动脚本
set -e

# 根据环境变量决定启动什么服务
SERVICE_TYPE=${SERVICE_TYPE:-web}

echo "=== Pulse Guard 启动脚本 ==="
echo "SERVICE_TYPE: $SERVICE_TYPE"
echo "当前目录: $(pwd)"
echo "Python 版本: $(python --version)"
echo "=========================="

case "$SERVICE_TYPE" in
    web)
        echo "启动 Web 服务..."
        exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
        ;;
    worker)
        echo "启动 Worker 服务..."
        echo "启动 Celery Worker..."
        exec celery -A backend.worker.celery_app worker --loglevel=info
        ;;
    *)
        echo "未知服务类型: $SERVICE_TYPE"
        echo "支持的类型: web, worker"
        exit 1
        ;;
esac
