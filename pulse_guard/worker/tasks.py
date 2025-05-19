"""
Celery 任务定义模块。
"""
import logging
from typing import Dict, Any

from pulse_guard.agent.graph import run_code_review
from pulse_guard.worker.celery_app import celery_app

# 配置日志
logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, name="pulse_guard.worker.tasks.process_pull_request")
def process_pull_request(self, repo: str, pr_number: int) -> Dict[str, Any]:
    """处理 Pull Request

    Args:
        repo: 仓库名称，格式为 "owner/repo"
        pr_number: Pull Request 编号

    Returns:
        处理结果
    """
    try:
        logger.info(f"Processing PR #{pr_number} from {repo}")

        # 运行代码审查
        result = run_code_review({
            "repo": repo,
            "number": pr_number
        })

        logger.info(f"Completed review for PR #{pr_number} from {repo}")
        return {
            "status": "success",
            "pr_number": pr_number,
            "repo": repo,
            "file_count": len(result.get("file_reviews", [])),
            "issue_count": sum(len(review.get("issues", [])) for review in result.get("file_reviews", []))
        }
    except Exception as e:
        logger.error(f"Error processing PR #{pr_number} from {repo}: {str(e)}")
        # 重试任务
        self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        return {
            "status": "error",
            "pr_number": pr_number,
            "repo": repo,
            "error": str(e)
        }
