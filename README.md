# Pulse Guard

自动化 PR 代码质量审查工具，基于 LangChain + LangGraph + Deepseek LLM。

## 功能特点

- 监听 GitHub PR Webhook 事件
- 自动拉取 PR 的 diff、commit 信息
- 基于 LangChain + Deepseek LLM 进行代码质量分析
- 自动将分析结果评论到 PR
- 支持异步后台处理，主线程快速响应

## 技术栈

- **Web 框架**: FastAPI
- **LLM 集成**: LangChain + LangGraph
- **异步处理**: Celery + Redis
- **GitHub 交互**: GitHub REST API

## 项目结构

```
pulse_guard/
├── __init__.py
├── api/                # API 相关模块
│   ├── __init__.py
│   ├── routes.py       # API 路由定义
│   └── webhook.py      # GitHub webhook 处理
├── llm/                # LLM 相关模块
│   ├── __init__.py
│   ├── client.py       # LLM 客户端
│   └── prompts.py      # 提示模板
├── agent/              # Agent 相关模块
│   ├── __init__.py
│   └── graph.py        # LangGraph 定义
├── tools/              # 工具函数模块
│   ├── __init__.py
│   └── github.py       # GitHub 工具
├── models/             # 数据模型模块
│   ├── __init__.py
│   ├── github.py       # GitHub 数据模型
│   └── review.py       # 审查结果模型
├── worker/             # 异步任务模块
│   ├── __init__.py
│   ├── celery_app.py   # Celery 配置
│   └── tasks.py        # 任务定义
├── config.py           # 配置管理
└── main.py             # 应用入口
```

## 安装与配置

### 前置条件

- Python 3.12+
- Redis

### 安装依赖

使用 uv (推荐):

```bash
# 安装 uv (如果尚未安装)
curl -sSf https://install.uv.dev | sh

# 使用 uv 安装项目依赖
uv pip install -e .

# 或者安装开发依赖
uv pip install -e ".[dev]"
```

使用传统的 pip:

```bash
pip install -e .
```

### 配置

1. 复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

2. 编辑 `config.toml` 文件配置应用参数。

### 重要配置项

#### 开发模式配置

在开发环境中，您可以启用开发模式，以简化测试过程。在 `config.toml` 中设置：

```toml
[github]
development_mode = true          # 启用开发模式
verify_webhook_signature = false  # 禁用签名验证
```

开发模式的特点：

1. **宽松的请求验证**：即使缺少必要的头信息或 JSON 负载无效，也不会拒绝请求
2. **默认值填充**：自动为缺失的头信息和负载生成默认值
3. **详细的日志**：提供更多调试信息

在生产环境中，应禁用开发模式并启用签名验证：

```toml
[github]
development_mode = false         # 禁用开发模式
verify_webhook_signature = true  # 启用签名验证
```

并确保在 `.env` 文件中设置了 `WEBHOOK_SECRET`。

## 使用方法

### 使用 Makefile

项目提供了 Makefile 来简化常见操作：

```bash
# 安装依赖
make install

# 安装开发依赖
make dev

# 运行代码检查
make lint

# 格式化代码
make format

# 运行测试
make test

# 启动 Web 服务
make run

# 启动 Celery Worker
make worker

# Docker 相关
make docker-build
make docker-up
make docker-down
make docker-logs

# 初始化数据库
make init-db

# 运行演示
make demo
```

### 手动启动应用

使用 uv (推荐):

```bash
# 安装依赖
uv sync

# 启动 Web 服务
uv run uvicorn pulse_guard.main:app --host 0.0.0.0 --port 8000

# 启动 Celery Worker
uv run python celery_worker.py
```

### Docker 部署

```bash
# 构建并启动所有服务
make docker-build
make docker-up

# 查看服务状态
make docker-logs

# 停止服务
make docker-down
```

### 本地开发工作流程

在本地进行开发时，您需要同时运行多个服务并使用 ngrok 创建公网访问点。以下是建议的工作流程：

1. **启动 Redis**（如果尚未运行）：

```bash
redis-server
```

2. **启动 Web 服务**（在一个终端窗口）：

```bash
make run
```

3. **启动 Celery Worker**（在另一个终端窗口）：

```bash
make worker
```

4. **启动 ngrok**（在第三个终端窗口）：

```bash
make ngrok
```

5. **配置 GitHub Webhook**：
   - 使用 ngrok 提供的公网 URL 配置 GitHub webhook
   - 测试 webhook 触发

### 使用 ngrok 进行本地开发

在本地开发时，您需要使用 ngrok 等工具创建一个公网可访问的 URL，以便 GitHub 可以将 webhook 请求发送到您的本地服务器。

1. 安装 ngrok（如果尚未安装）：

```bash
# 使用 Homebrew 安装（macOS）
brew install ngrok

# 或者从官网下载：https://ngrok.com/download
```

2. 启动 ngrok：

```bash
# 将本地的 8000 端口映射到公网
ngrok http 8000
```

3. ngrok 启动后，它会显示一个公网 URL（如 `https://1234abcd.ngrok.io`），记下这个 URL。

### 配置 GitHub Webhook

1. 在 GitHub 仓库设置中添加 Webhook
2. 设置 Payload URL 为 `https://your-ngrok-url/api/webhook/github`（如果使用 ngrok）或 `http://your-server/api/webhook/github`（生产环境）
3. 选择 Content type 为 `application/json`
4. 设置 Secret（与 `.env` 中的 `WEBHOOK_SECRET` 一致）
5. 选择 "Let me select individual events" 并勾选 "Pull requests"

### 手动触发审查

可以通过 API 手动触发代码审查：

```bash
curl -X POST "http://localhost:8000/api/review?repo=owner/repo&pr_number=123"
```

## 扩展性

Pulse Guard 设计具有高度可扩展性：

- **LLM 提供者**: 通过配置文件轻松切换不同的 LLM
- **代码审查类型**: 可以添加新的审查类型
- **Git 平台**: 架构支持扩展到其他 Git 平台

## 许可证

MIT
