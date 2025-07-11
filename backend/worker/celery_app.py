"""
Celery 应用配置模块。
"""

from celery import Celery

from backend.config import config

# 创建 Celery 应用
celery_app = Celery("backend", broker=config.redis.url, backend=config.redis.url)

# 配置 Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# 自动发现任务
celery_app.autodiscover_tasks(["backend.worker"])
