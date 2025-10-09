"""
Gitea 相关的数据模型。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# 配置日志
logger = logging.getLogger(__name__)


class GiteaUser(BaseModel):
    """Gitea 用户模型"""

    id: int
    login: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    language: Optional[str] = None
    is_admin: Optional[bool] = None
    username: Optional[str] = None


class GiteaRepository(BaseModel):
    """Gitea 仓库模型"""

    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    private: bool = False
    html_url: str
    clone_url: str
    default_branch: Optional[str] = None


class GiteaBranch(BaseModel):
    """Gitea 分支模型"""

    label: str
    ref: str
    sha: str
    repo: Optional[GiteaRepository] = None


class GiteaFile(BaseModel):
    """Gitea 文件模型"""

    filename: str
    status: Optional[str] = None  # added, modified, removed, renamed
    additions: int = 0
    deletions: int = 0
    changes: Optional[int] = None
    patch: Optional[Any] = None  # 可能是字符串或字典格式
    html_url: Optional[str] = None
    raw_url: Optional[str] = None
    contents_url: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def compute_defaults(cls, data: Any) -> Any:
        """在验证前计算默认值"""
        if isinstance(data, dict):
            # 设置 status 默认值
            if data.get("status") is None:
                data["status"] = "modified"

            # 计算 changes 字段
            if data.get("changes") is None:
                additions = data.get("additions", 0)
                deletions = data.get("deletions", 0)
                data["changes"] = additions + deletions

        return data

    @field_validator("patch")
    @classmethod
    def validate_patch(cls, v):
        """验证并处理 patch 字段"""
        if isinstance(v, dict):
            # 如果是字典，尝试提取 diff 字段
            return v.get("diff")
        elif isinstance(v, str):
            # 如果是字符串，直接返回
            return v
        else:
            # 其他情况返回 None
            return None


class PullRequest(BaseModel):
    """Gitea Pull Request 模型"""

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
    user: GiteaUser
    head: Dict[str, Any]  # 包含 sha, ref, repo 等信息
    base: Dict[str, Any]  # 包含 sha, ref, repo 等信息
    merged: Optional[bool] = None
    mergeable: Optional[bool] = None
    draft: Optional[bool] = False
    additions: Optional[int] = 0
    deletions: Optional[int] = 0
    changed_files: Optional[int] = 0

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


class FileContent(BaseModel):
    """Gitea 文件内容模型"""

    name: str
    path: str
    sha: str
    type: str  # file, dir, submodule
    size: int
    encoding: Optional[str] = None
    content: Optional[str] = None
    url: str
    html_url: str
    download_url: Optional[str] = None


class CommitPerson(BaseModel):
    """Gitea 提交人模型"""

    name: str
    email: str
    date: str


class CommitDetail(BaseModel):
    """Gitea 提交详情模型"""

    url: str
    author: CommitPerson
    committer: CommitPerson
    message: str


class CommitItem(BaseModel):
    """Gitea 提交项模型"""

    url: str
    sha: str
    html_url: str
    commit: CommitDetail
    author: Optional[GiteaUser] = None
    committer: Optional[GiteaUser] = None


class WebhookConfig(BaseModel):
    """Gitea webhook 配置模型"""

    content_type: str
    url: str


class Webhook(BaseModel):
    """Gitea webhook 模型"""

    id: int
    type: str
    config: WebhookConfig
    events: List[str]
    active: bool
    created_at: str
    updated_at: str


class ReviewComment(BaseModel):
    """代码审查评论模型"""

    body: str
    path: Optional[str] = None
    position: Optional[int] = None
    commit_id: Optional[str] = None
