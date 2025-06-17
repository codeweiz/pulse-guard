"""
Gitee API 客户端和工具函数。
"""
import hashlib
import hmac
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

import requests
from langchain.tools import tool

from pulse_guard.config import config
from pulse_guard.models.gitee import GiteeFile, PullRequest, ReviewComment

# 配置日志
logger = logging.getLogger(__name__)


class GiteeClient:
    """Gitee API 客户端"""

    def __init__(self):
        """初始化 Gitee 客户端"""
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

    def get_pull_request(self, repo: str, pr_number: int) -> PullRequest:
        """获取 Pull Request 信息

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号

        Returns:
            Pull Request 信息
        """
        response = self._make_request("GET", f"/repos/{repo}/pulls/{pr_number}")
        data = response.json()

        # 转换日期字段
        for date_field in ["created_at", "updated_at", "closed_at", "merged_at"]:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field].replace("Z", "+00:00"))

        return PullRequest(**data)

    def get_pull_request_files(self, repo: str, pr_number: int) -> List[GiteeFile]:
        """获取 Pull Request 修改的文件列表

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号

        Returns:
            文件列表
        """
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

        return processed_files

    def get_file_content(self, repo: str, file_path: str, ref: str) -> str:
        """获取文件内容

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            file_path: 文件路径
            ref: 分支或提交 SHA

        Returns:
            文件内容
        """
        response = self._make_request(
            "GET",
            f"/repos/{repo}/contents/{file_path}",
            params={"ref": ref}
        )
        data = response.json()

        import base64
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content

    def create_pull_request_comment(self, repo: str, pr_number: int, body: str) -> Dict[str, Any]:
        """创建 Pull Request 评论

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号
            body: 评论内容

        Returns:
            评论信息
        """
        response = self._make_request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/comments",
            json={"body": body}
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

    def verify_webhook_signature(self, payload: bytes, signature: Optional[str]) -> bool:
        """验证 Webhook 签名

        Args:
            payload: 请求体
            signature: Gitee 签名

        Returns:
            是否验证通过
        """
        try:
            # 检查是否需要验证签名
            if not config.gitee.verify_webhook_signature:
                logger.info("Webhook signature verification is disabled in config")
                return True

            if not config.gitee.webhook_secret:
                logger.warning("Webhook secret not configured, skipping signature verification")
                return True  # 如果没有设置密钥，则跳过验证

            if not signature:
                logger.warning("No signature provided in request")
                return False

            # 计算签名
            secret = config.gitee.webhook_secret.encode()
            hmac_obj = hmac.new(secret, payload, hashlib.sha256)
            expected_signature = hmac_obj.hexdigest()

            # 验证签名
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False


# 创建 Gitee 客户端实例
gitee_client = GiteeClient()


@tool
def get_gitee_pr_info(input: str) -> Dict[str, Any]:
    """获取 Gitee Pull Request 的基本信息

    Args:
        input: 输入格式："owner/repo|pr_number"

    Returns:
        Pull Request 信息
    """
    # 解析输入
    repo, pr_number_str = input.split('|')
    pr_number = int(pr_number_str)
    pr = gitee_client.get_pull_request(repo, pr_number)
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


@tool
def get_gitee_pr_files(input: str) -> List[Dict[str, Any]]:
    """获取 Gitee Pull Request 修改的文件列表

    Args:
        input: 输入格式："owner/repo|pr_number"

    Returns:
        文件列表
    """
    # 解析输入
    repo, pr_number_str = input.split('|')
    pr_number = int(pr_number_str)
    files = gitee_client.get_pull_request_files(repo, pr_number)
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


@tool
def get_gitee_file_content(input: str) -> str:
    """获取 Gitee 仓库文件内容

    Args:
        input: 输入格式："owner/repo|file_path|ref"

    Returns:
        文件内容
    """
    # 解析输入
    repo, file_path, ref = input.split('|')
    return gitee_client.get_file_content(repo, file_path, ref)


@tool
def post_gitee_pr_comment(input: str) -> Dict[str, Any]:
    """发布 Gitee Pull Request 评论

    Args:
        input: 输入格式："owner/repo|pr_number|comment"

    Returns:
        评论信息
    """
    # 解析输入
    parts = input.split('|', 2)  # 最多分成2次，因为评论内容可能包含|符号
    if len(parts) != 3:
        raise ValueError("Input format should be 'owner/repo|pr_number|comment'")
    repo, pr_number_str, comment = parts
    pr_number = int(pr_number_str)
    return gitee_client.create_pull_request_comment(repo, pr_number, comment)
