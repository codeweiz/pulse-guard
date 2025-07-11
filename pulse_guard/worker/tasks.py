"""
Celery 任务定义模块。
"""

import logging
from typing import Any, Dict

from pulse_guard.agent.graph import run_code_review
from pulse_guard.worker.celery_app import celery_app

# 配置日志
logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True, max_retries=3, name="pulse_guard.worker.tasks.process_pull_request"
)
def process_pull_request(
    self, repo: str, pr_number: int, platform: str = "github"
) -> Dict[str, Any]:
    """处理 Pull Request

    Args:
        repo: 仓库名称，格式为 "owner/repo"
        pr_number: Pull Request 编号
        platform: 平台名称，"github" 或 "gitee"

    Returns:
        处理结果
        :param platform: 平台名称
        :param pr_number: PR 编号
        :param repo: 仓库
        :param self: 自身
    """
    try:
        logger.info(f"Processing PR #{pr_number} from {repo}")

        # 运行代码审查 - 使用简化工作流
        result = run_code_review(
            {"repo": repo, "number": pr_number, "platform": platform}
        )

        logger.info(f"Completed review for PR #{pr_number} from {repo}")

        # 安全地获取文件审查结果
        file_reviews = result.get("file_reviews", [])
        if not file_reviews:
            # 如果没有 file_reviews，尝试从 enhanced_analysis 中获取
            enhanced_analysis = result.get("enhanced_analysis", {})
            if enhanced_analysis and enhanced_analysis.get("file_results"):
                file_reviews = enhanced_analysis["file_results"]

        # 计算文件数量和问题数量
        file_count = len(file_reviews) if file_reviews else 0
        issue_count = 0
        if file_reviews:
            for review in file_reviews:
                if isinstance(review, dict):
                    issues = review.get("issues", [])
                    if isinstance(issues, list):
                        issue_count += len(issues)

        return {
            "status": "success",
            "pr_number": pr_number,
            "repo": repo,
            "platform": platform,
            "file_count": file_count,
            "issue_count": issue_count,
        }
    except Exception as e:
        logger.error(f"Error processing PR #{pr_number} from {repo}: {str(e)}")
        # 重试任务
        self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        return {
            "status": "error",
            "pr_number": pr_number,
            "repo": repo,
            "platform": platform,
            "error": str(e),
        }
