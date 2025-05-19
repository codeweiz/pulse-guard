"""
GitHub 相关的工具函数。
"""
import base64
import hmac
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from langchain.tools import tool

from pulse_guard.config import config
from pulse_guard.models.github import GitHubFile, PullRequest, ReviewComment

# 配置日志
logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API 客户端"""

    def __init__(self, token: Optional[str] = None, api_base_url: Optional[str] = None):
        """初始化 GitHub 客户端

        Args:
            token: GitHub API 令牌
            api_base_url: GitHub API 基础 URL
        """
        self.token = token or config.github.token
        self.api_base_url = api_base_url or config.github.api_base_url
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
                method=method,
                url=url,
                headers=self.headers,
                **kwargs
            )
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

    def get_pull_request_files(self, repo: str, pr_number: int) -> List[GitHubFile]:
        """获取 Pull Request 修改的文件列表

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号

        Returns:
            文件列表
        """
        response = self._make_request("GET", f"/repos/{repo}/pulls/{pr_number}/files")
        files_data = response.json()

        return [GitHubFile(**file_data) for file_data in files_data]

    def get_file_content(self, repo: str, path: str, ref: str) -> str:
        """获取文件内容

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            path: 文件路径
            ref: 分支、标签或提交 SHA

        Returns:
            文件内容
        """
        response = self._make_request(
            "GET",
            f"/repos/{repo}/contents/{path}",
            params={"ref": ref}
        )
        data = response.json()

        if data.get("type") != "file":
            raise ValueError(f"Path '{path}' is not a file")

        content = data.get("content", "")
        if content:
            # Base64 解码
            content = base64.b64decode(content).decode("utf-8")

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
            f"/repos/{repo}/issues/{pr_number}/comments",
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
            payload["comments"] = [comment.dict() for comment in comments]

        response = self._make_request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            json=payload
        )
        return response.json()

    def verify_webhook_signature(self, payload: bytes, signature, signature_type="sha256") -> bool:
        """验证 Webhook 签名

        Args:
            payload: 请求体
            signature: GitHub 签名
            signature_type: 签名类型，"sha1" 或 "sha256"

        Returns:
            是否验证通过
        """
        try:
            # 检查是否需要验证签名
            if not config.github.verify_webhook_signature:
                logger.info("Webhook signature verification is disabled in config")
                return True

            if not config.github.webhook_secret:
                logger.warning("Webhook secret not configured, skipping signature verification")
                return True  # 如果没有设置密钥，则跳过验证

            # 尝试将签名转换为字符串
            try:
                # 如果是 FastAPI 的 Header 对象，尝试获取实际值
                signature_str = str(signature)
                logger.debug(f"Converted signature to string: {signature_str}")
            except Exception as e:
                logger.error(f"Error converting signature to string: {str(e)}")
                return False

            # 检查签名格式
            expected_prefix = f"{signature_type}="
            if not signature_str.startswith(expected_prefix):
                logger.error(f"Invalid signature format: {signature_str}, expected prefix: {expected_prefix}")
                return False

            # 计算 HMAC
            secret = config.github.webhook_secret.encode()
            signature_hash = hmac.new(secret, payload, signature_type).hexdigest()
            expected_signature = f"{signature_type}={signature_hash}"

            # 比较签名
            result = hmac.compare_digest(expected_signature, signature_str)
            if result:
                logger.debug("Signature verification successful")
            else:
                logger.warning(f"Signature verification failed. Expected: {expected_signature}, Got: {signature_str}")

            return result
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False


# 创建 GitHub 客户端实例
github_client = GitHubClient()


@tool
def get_pr_info(input: str) -> Dict[str, Any]:
    """获取 Pull Request 的基本信息

    Args:
        input: 输入格式："owner/repo|pr_number"

    Returns:
        Pull Request 信息
    """
    # 解析输入
    repo, pr_number_str = input.split('|')
    pr_number = int(pr_number_str)
    pr = github_client.get_pull_request(repo, pr_number)
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
def get_pr_files(input: str) -> List[Dict[str, Any]]:
    """获取 Pull Request 修改的文件列表

    Args:
        input: 输入格式："owner/repo|pr_number"

    Returns:
        文件列表
    """
    # 解析输入
    repo, pr_number_str = input.split('|')
    pr_number = int(pr_number_str)
    files = github_client.get_pull_request_files(repo, pr_number)
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
def get_file_content(input: str) -> str:
    """获取文件内容

    Args:
        input: 输入格式："owner/repo|file_path|ref"

    Returns:
        文件内容
    """
    # 解析输入
    parts = input.split('|')
    if len(parts) != 3:
        raise ValueError("Input format should be 'owner/repo|file_path|ref'")
    repo, file_path, ref = parts
    return github_client.get_file_content(repo, file_path, ref)


@tool
def post_pr_comment(input: str) -> Dict[str, Any]:
    """发布 Pull Request 评论

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
    return github_client.create_pull_request_comment(repo, pr_number, comment)
