"""
GitHub 平台提供者实现。
"""
import logging
from typing import Dict, List, Any

from .base import PlatformProvider
from .factory import register_platform
from ..tools.github import github_client

logger = logging.getLogger(__name__)


@register_platform("github")
class GitHubProvider(PlatformProvider):
    """GitHub 平台提供者实现"""

    def __init__(self, platform_name: str):
        super().__init__(platform_name)
        self.client = github_client

    def get_pr_info(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """获取 GitHub Pull Request 基本信息"""
        logger.debug(f"Getting GitHub PR info: {repo}#{pr_number}")

        pr = self.client.get_pull_request(repo, pr_number)
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

        files = self.client.get_pull_request_files(repo, pr_number)
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

        return self.client.get_file_content(repo, file_path, ref)

    def post_pr_comment(self, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """发布 GitHub Pull Request 评论"""
        logger.debug(f"Posting GitHub PR comment: {repo}#{pr_number}")

        return self.client.create_pull_request_comment(repo, pr_number, comment)

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """验证 GitHub Webhook 签名"""
        logger.debug("Verifying GitHub webhook signature")

        return self.client.verify_webhook_signature(payload, signature)
