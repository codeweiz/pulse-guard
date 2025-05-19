#!/usr/bin/env python
"""
Celery worker 启动脚本。
"""
import sys

from pulse_guard.worker.celery_app import celery_app

if __name__ == "__main__":
    # 检查命令行参数，如果没有 'worker' 参数，则添加
    if len(sys.argv) <= 1 or sys.argv[1] != 'worker':
        sys.argv = [sys.argv[0]] + ['worker', '--loglevel=info'] + sys.argv[1:]
    celery_app.worker_main(argv=sys.argv)
