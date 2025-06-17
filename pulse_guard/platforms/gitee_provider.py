"""
Gitee 平台提供者实现。
"""
import base64
import logging
from datetime import datetime
from typing import Dict, List, Any

import requests

from .base import PlatformProvider
from .factory import register_platform
from ..config import config
from ..models.gitee import GiteeFile, PullRequest, ReviewComment

logger = logging.getLogger(__name__)


@register_platform("gitee")
class GiteeProvider(PlatformProvider):
    """Gitee 平台提供者实现"""

    def __init__(self, platform_name: str):
        super().__init__(platform_name)
        # 初始化 Gitee API 客户端配置
        self.api_base_url = config.gitee.api_base_url
        self.access_token = config.gitee.access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """发送 API 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            **kwargs: 请求参数

        Returns:
            响应对象
        """
        # 添加 access_token 到请求参数
        params = kwargs.get("params", {})
        params["access_token"] = self.access_token
        kwargs["params"] = params

        url = f"{self.api_base_url}{endpoint}"
        logger.debug(f"Making {method} request to {url}")

        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()

        return response

    def get_pr_info(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """获取 Gitee Pull Request 基本信息"""
        logger.debug(f"Getting Gitee PR info: {repo}#{pr_number}")

        response = self._make_request("GET", f"/repos/{repo}/pulls/{pr_number}")
        data = response.json()

        # 转换日期字段
        for date_field in ["created_at", "updated_at", "closed_at", "merged_at"]:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field].replace("Z", "+00:00"))

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
        """获取 Gitee Pull Request 修改的文件列表"""
        logger.debug(f"Getting Gitee PR files: {repo}#{pr_number}")

        response = self._make_request("GET", f"/repos/{repo}/pulls/{pr_number}/files")
        files_data = response.json()

        processed_files = []
        for file_data in files_data:
            # 记录原始数据用于调试
            logger.debug(f"Processing file data: {file_data}")

            try:
                # 现在 GiteeFile 模型可以自动处理数据验证和转换
                processed_files.append(GiteeFile(**file_data))
            except Exception as e:
                logger.error(f"Error creating GiteeFile from data {file_data}: {str(e)}")
                # 跳过有问题的文件，继续处理其他文件
                continue

        return [
            {
                "filename": file.filename,
                "status": file.status,
                "additions": file.additions,
                "deletions": file.deletions,
                "changes": file.changes,
                "patch": file.patch,
            }
            for file in processed_files
        ]

    def get_file_content(self, repo: str, file_path: str, ref: str) -> str:
        """获取 Gitee 文件内容"""
        logger.debug(f"Getting Gitee file content: {repo}/{file_path}@{ref}")

        response = self._make_request(
            "GET",
            f"/repos/{repo}/contents/{file_path}",
            params={"ref": ref}
        )
        data = response.json()

        content = base64.b64decode(data["content"]).decode("utf-8")
        return content

    def post_pr_comment(self, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """发布 Gitee Pull Request 评论"""
        logger.debug(f"Posting Gitee PR comment: {repo}#{pr_number}")

        response = self._make_request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/comments",
            json={"body": comment}
        )
        return response.json()

    def create_pull_request_review(
            self, repo: str, pr_number: int, commit_id: str, body: str, comments: List[ReviewComment]
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
            payload["comments"] = [comment.model_dump() for comment in comments]

        response = self._make_request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            json=payload
        )
        return response.json()
