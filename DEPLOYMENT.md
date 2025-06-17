# Pulse Guard 一键部署指南

## 🚀 快速开始

### 1. 准备环境

确保已安装：
- Docker
- Docker Compose

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件，填入必要的 API 密钥
vim .env
```

**必须配置的环境变量：**
- `GITHUB_TOKEN`: GitHub API 令牌
- `DEEPSEEK_API_KEY`: Deepseek API 密钥

### 3. 一键部署

```bash
# 启动所有服务
./deploy.sh

# 或者
./deploy.sh start
```

### 4. 验证部署

```bash
# 检查服务状态
./deploy.sh status

# 查看日志
./deploy.sh logs

# 访问应用
curl http://localhost:8000/api/health
```

## 📋 服务架构

部署包含以下服务：
- **web**: FastAPI Web 服务 (端口 8000)
- **worker**: Celery Worker 后台任务处理
- **redis**: Redis 消息队列

## 🔧 常用命令

```bash
# 启动服务
./deploy.sh start

# 停止服务
./deploy.sh stop

# 重启服务
./deploy.sh restart

# 查看日志
./deploy.sh logs

# 查看状态
./deploy.sh status
```

## 🔧 手动 Docker 命令

如果不使用部署脚本，也可以直接使用 Docker Compose：

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f

# 查看状态
docker-compose ps
```

## ⚙️ 配置说明

### 必需的环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `GITHUB_TOKEN` | GitHub API 令牌 | `ghp_xxxxxxxxxxxx` |
| `DEEPSEEK_API_KEY` | Deepseek API 密钥 | `sk-xxxxxxxxxxxx` |

### 可选的环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `REDIS_URL` | Redis 连接URL | `redis://redis:6379/0` |
| `WEBHOOK_SECRET` | GitHub Webhook 密钥 | - |
| `GITEE_ACCESS_TOKEN` | Gitee API 令牌 | - |

## 🔍 故障排除

### 常见问题

1. **服务启动失败**
   ```bash
   # 查看详细日志
   ./deploy.sh logs

   # 检查配置
   cat .env
   ```

2. **无法访问服务**
   ```bash
   # 检查端口是否被占用
   lsof -i :8000

   # 检查服务状态
   ./deploy.sh status
   ```

3. **Redis 连接失败**
   ```bash
   # 检查 Redis 容器
   docker-compose ps redis

   # 重启 Redis
   docker-compose restart redis
   ```

### 获取帮助

如需更多帮助，请查看项目的 [README.md](README.md) 或提交 Issue。
