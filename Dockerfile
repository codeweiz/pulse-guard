# Pulse Guard Docker 镜像
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 8000

# 健康检查 (只对 web 服务有效)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD if [ "$SERVICE_TYPE" = "worker" ]; then python -c "from pulse_guard.worker.celery_app import celery_app; celery_app.control.inspect().ping()"; else curl -f http://localhost:8000/api/health; fi || exit 1

# 启动脚本
COPY start.sh /start.sh
RUN chmod +x /start.sh

# 默认启动命令
CMD ["/start.sh"]
