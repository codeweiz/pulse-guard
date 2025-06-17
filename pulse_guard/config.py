"""
配置管理模块，负责加载和提供应用配置。
"""
import os
from pathlib import Path
from typing import List

import tomli
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 加载环境变量
load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent

# 加载 TOML 配置
try:
    with open(ROOT_DIR / "config.toml", "rb") as f:
        toml_config = tomli.load(f)
except FileNotFoundError:
    toml_config = {"llm": {}, "github": {}, "gitee": {}, "review": {}}


class LLMConfig(BaseModel):
    """LLM 配置"""
    provider: str = Field(
        default=toml_config.get("llm", {}).get("provider", "deepseek"),
        description="LLM 提供者"
    )
    model_name: str = Field(
        default=toml_config.get("llm", {}).get("model_name", "deepseek-coder"),
        description="LLM 模型名称"
    )
    api_key: str = Field(
        default=os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        description="LLM API 密钥"
    )


class GitHubConfig(BaseModel):
    """GitHub 配置"""
    api_base_url: str = Field(
        default=toml_config.get("github", {}).get("api_base_url", "https://api.github.com"),
        description="GitHub API 基础 URL"
    )
    token: str = Field(
        default=os.getenv("GITHUB_TOKEN", ""),
        description="GitHub API 令牌"
    )
    webhook_secret: str = Field(
        default=os.getenv("WEBHOOK_SECRET", ""),
        description="Webhook 密钥"
    )


class ReviewConfig(BaseModel):
    """代码审查配置"""
    types: List[str] = Field(
        default=toml_config.get("review", {}).get("types", ["code_quality", "security", "best_practices"]),
        description="审查类型"
    )
    max_files_per_review: int = Field(
        default=toml_config.get("review", {}).get("max_files_per_review", 10),
        description="每次审查的最大文件数"
    )


class RedisConfig(BaseModel):
    """Redis 配置"""
    url: str = Field(
        default=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        description="Redis URL"
    )


class GiteeConfig(BaseModel):
    """Gitee 配置"""
    api_base_url: str = Field(
        default=toml_config.get("gitee", {}).get("api_base_url", "https://gitee.com/api/v5"),
        description="Gitee API 基础 URL"
    )
    access_token: str = Field(
        default=os.getenv("GITEE_ACCESS_TOKEN", ""),
        description="Gitee API 访问令牌"
    )
    webhook_secret: str = Field(
        default=os.getenv("GITEE_WEBHOOK_SECRET", ""),
        description="Gitee Webhook 密钥"
    )


class Config(BaseModel):
    """应用配置"""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    gitee: GiteeConfig = Field(default_factory=GiteeConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)


# 全局配置实例
config = Config()
