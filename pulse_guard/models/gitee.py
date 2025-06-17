"""
Gitee 相关的数据模型。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, field_validator

# 配置日志
logger = logging.getLogger(__name__)


class GiteeUser(BaseModel):
    """Gitee 用户模型"""
    id: int
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    type: Optional[str] = None
    site_admin: Optional[bool] = None
    username: Optional[str] = None
    user_name: Optional[str] = None
    url: Optional[str] = None


class GiteeFile(BaseModel):
    """Gitee 文件模型"""
    filename: str
    status: Optional[str] = None  # 可能为 None，added, modified, removed
    additions: int = 0
    deletions: int = 0
    changes: Optional[int] = None  # 可能不存在，需要计算
    patch: Optional[Any] = None  # 可能是字符串或字典格式
    blob_url: Optional[str] = None
    raw_url: Optional[str] = None

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        """验证并修复 status 字段"""
        if v is None:
            return "modified"  # 默认值
        return v

    @field_validator('changes')
    @classmethod
    def validate_changes(cls, v, info):
        """验证并计算 changes 字段"""
        if v is None:
            # 如果 changes 为 None，从 additions 和 deletions 计算
            data = info.data
            additions = data.get('additions', 0)
            deletions = data.get('deletions', 0)
            return additions + deletions
        return v

    @field_validator('patch')
    @classmethod
    def validate_patch(cls, v):
        """验证并处理 patch 字段"""
        if isinstance(v, dict):
            # 如果是字典，尝试提取 diff 字段
            return v.get('diff')
        elif isinstance(v, str):
            # 如果是字符串，直接返回
            return v
        else:
            # 其他情况返回 None
            return None


class PullRequest(BaseModel):
    """Pull Request 模型"""
    id: int
    number: int
    title: str
    body: Optional[str] = None
    state: str  # open, closed
    html_url: str
    diff_url: str
    patch_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    user: GiteeUser
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

    @field_validator('event_type', 'delivery_id', 'signature')
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
                if info.field_name == 'signature':
                    return None  # signature 可以为 None
                return ""  # 其他字段返回空字符串
        return "" if info.field_name != 'signature' else None

    @property
    def is_pull_request_event(self) -> bool:
        """是否为 Pull Request 事件"""
        return self.event_type == "Merge Request Hook"

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
