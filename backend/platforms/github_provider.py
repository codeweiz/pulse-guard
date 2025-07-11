"""
GitHub 平台提供者实现。
"""

import base64
import logging
from datetime import datetime
from typing import Any, Dict, List

import httpx

from ..config import config
from ..models.github import GitHubFile, PullRequest, ReviewComment
from .base import PlatformProvider
from .factory import register_platform

logger = logging.getLogger(__name__)


@register_platform("github")
class GitHubProvider(PlatformProvider):
    """GitHub 平台提供者实现"""

    def __init__(self, platform_name: str):
        super().__init__(platform_name)
        # 初始化 GitHub API 客户端配置
        self.token = config.github.token
        self.api_base_url = config.github.api_base_url
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}",
        }

    def _make_request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """发送 HTTP 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            **kwargs: 其他参数

        Returns:
            HTTP 响应
        """
        url = f"{self.api_base_url}{endpoint}"
        with httpx.Client() as client:
            response = client.request(
                method=method, url=url, headers=self.headers, **kwargs
            )
            response.raise_for_status()
            return response

    def get_pr_info(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """获取 GitHub Pull Request 基本信息"""
        logger.debug(f"Getting GitHub PR info: {repo}#{pr_number}")

        response = self._make_request("GET", f"/repos/{repo}/pulls/{pr_number}")
        data = response.json()

        # 转换日期字段
        for date_field in ["created_at", "updated_at", "closed_at", "merged_at"]:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(
                    data[date_field].replace("Z", "+00:00")
                )

        pr = PullRequest(**data)
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body,
            "state": pr.state,
            "user": pr.user.login,
            "html_url": pr.html_url,
            "created_at": pr.created_at.isoformat(),
            "updated_at": pr.updated_at.isoformat(),
            "head_sha": pr.head_sha,
            "base_sha": pr.base_sha,
            "repo_full_name": pr.repo_full_name,
        }

    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """获取 GitHub Pull Request 修改的文件列表"""
        logger.debug(f"Getting GitHub PR files: {repo}#{pr_number}")

        response = self._make_request("GET", f"/repos/{repo}/pulls/{pr_number}/files")
        files_data = response.json()

        files = [GitHubFile(**file_data) for file_data in files_data]
        return [
            {
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": file.patch,
            }
            for file in files
        ]

    def get_file_content(self, repo: str, file_path: str, ref: str) -> str:
        """获取 GitHub 文件内容"""
        logger.debug(f"Getting GitHub file content: {repo}/{file_path}@{ref}")

        response = self._make_request(
            "GET", f"/repos/{repo}/contents/{file_path}", params={"ref": ref}
        )
        data = response.json()

        if data.get("type") != "file":
            raise ValueError(f"Path '{file_path}' is not a file")

        content = data.get("content", "")
        if content:
            # Base64 解码
            content = base64.b64decode(content).decode("utf-8")

        return content

    def post_pr_comment(
        self, repo: str, pr_number: int, comment: str
    ) -> Dict[str, Any]:
        """发布 GitHub Pull Request 评论"""
        logger.debug(f"Posting GitHub PR comment: {repo}#{pr_number}")

        response = self._make_request(
            "POST", f"/repos/{repo}/issues/{pr_number}/comments", json={"body": comment}
        )
        return response.json()

    def create_pull_request_review(
        self,
        repo: str,
        pr_number: int,
        commit_id: str,
        body: str,
        comments: List[ReviewComment],
    ) -> Dict[str, Any]:
        """创建 Pull Request 审查

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号
            commit_id: 提交 ID
            body: 审查内容
            comments: 行内评论列表

        Returns:
            审查信息
        """
        payload = {
            "commit_id": commit_id,
            "body": body,
            "event": "COMMENT",  # 可选值: APPROVE, REQUEST_CHANGES, COMMENT
        }

        if comments:
            payload["comments"] = [comment.dict() for comment in comments]

        response = self._make_request(
            "POST", f"/repos/{repo}/pulls/{pr_number}/reviews", json=payload
        )
        return response.json()
