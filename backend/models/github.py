"""
GitHub 相关的数据模型。
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, field_validator

# 配置日志
logger = logging.getLogger(__name__)


class GitHubUser(BaseModel):
    """GitHub 用户模型"""

    id: int
    login: str
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub 仓库模型"""

    id: int
    name: str
    full_name: str
    owner: GitHubUser
    html_url: str
    description: Optional[str] = None
    private: bool = False


class GitHubCommit(BaseModel):
    """GitHub 提交模型"""

    sha: str
    message: str
    author: GitHubUser
    url: str
    date: datetime


class GitHubFile(BaseModel):
    """GitHub 文件模型"""

    filename: str
    status: str  # added, modified, removed
    additions: int
    deletions: int
    changes: int
    blob_url: Optional[str] = None
    raw_url: Optional[str] = None
    contents_url: Optional[str] = None
    patch: Optional[str] = None
    content: Optional[str] = None


class PullRequest(BaseModel):
    """Pull Request 模型"""

    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str  # open, closed
    html_url: str
    diff_url: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    user: GitHubUser
    head: Dict[str, Any]  # 包含 sha, ref, repo 等信息
    base: Dict[str, Any]  # 包含 sha, ref, repo 等信息
    merged: Optional[bool] = None
    mergeable: Optional[bool] = None

    @property
    def repo_full_name(self) -> str:
        """获取仓库全名"""
        return self.base.get("repo", {}).get("full_name", "")

    @property
    def head_sha(self) -> str:
        """获取 head commit SHA"""
        return self.head.get("sha", "")

    @property
    def base_sha(self) -> str:
        """获取 base commit SHA"""
        return self.base.get("sha", "")


class WebhookEvent(BaseModel):
    """Webhook 事件模型"""

    event_type: str
    delivery_id: str
    signature: Optional[Any] = None
    payload: Dict[str, Any]

    @field_validator("event_type", "delivery_id", "signature")
    @classmethod
    def validate_headers(cls, v, info):
        """Convert header values to strings"""
        if v is not None:
            try:
                # 尝试将值转换为字符串
                str_value = str(v)
                logger.debug(f"Converted {info.field_name} to string: {str_value}")
                return str_value
            except Exception as e:
                logger.error(f"Error converting {info.field_name} to string: {str(e)}")
                if info.field_name == "signature":
                    return None  # signature 可以为 None
                return ""  # 其他字段返回空字符串
        return "" if info.field_name != "signature" else None

    @property
    def is_pull_request_event(self) -> bool:
        """是否为 Pull Request 事件"""
        return self.event_type == "pull_request"

    @property
    def action(self) -> str:
        """获取事件动作"""
        return self.payload.get("action", "")

    @property
    def pull_request(self) -> Optional[PullRequest]:
        """获取 Pull Request 信息"""
        if not self.is_pull_request_event:
            return None

        pr_data = self.payload.get("pull_request")
        if not pr_data:
            return None

        return PullRequest(**pr_data)


class ReviewComment(BaseModel):
    """代码审查评论模型"""

    body: str
    path: Optional[str] = None
    position: Optional[int] = None
    commit_id: Optional[str] = None
