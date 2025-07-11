# Pulse Guard Docker 镜像
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_CACHE_DIR=/tmp/.uv-cache

# 配置APT使用清华镜像源（加速系统包下载）
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖（合并为单层，减少镜像大小）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# 配置pip使用清华镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip config set global.extra-index-url "https://mirrors.aliyun.com/pypi/simple/"

# 安装uv（使用清华源）
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn uv

# 配置uv使用清华镜像源
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple/
ENV UV_EXTRA_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 创建非root用户（安全性提升）
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# 设置工作目录
WORKDIR /app

# 创建必要目录并设置权限
RUN mkdir -p logs && \
    chown -R appuser:appuser /app

# 复制项目配置文件（优化Docker缓存）
COPY --chown=appuser:appuser pyproject.toml .

# 安装Python依赖（使用清华源）
RUN uv pip install --system -e . && \
    rm -rf /tmp/.uv-cache

# 复制启动脚本
COPY --chown=appuser:appuser start.sh /start.sh
RUN chmod +x /start.sh

# 切换到非root用户
USER appuser

# 复制应用代码（放在最后以优化构建缓存）
COPY --chown=appuser:appuser . .

# 暴露端口
EXPOSE 8000

# 健康检查（优化超时时间）
HEALTHCHECK --interval=30s --timeout=15s --start-period=60s --retries=3 \
    CMD if [ "$SERVICE_TYPE" = "worker" ]; then \
        timeout 10 python -c "from pulse_guard.worker.celery_app import celery_app; celery_app.control.inspect().ping()" 2>/dev/null; \
    else \
        curl -f --max-time 10 http://localhost:8000/api/health 2>/dev/null; \
    fi || exit 1

# 默认启动命令
CMD ["/start.sh"]