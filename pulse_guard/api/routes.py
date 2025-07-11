"""
API 路由定义模块。
"""

from fastapi import APIRouter, Request

from pulse_guard.api.analytics import router as analytics_router
from pulse_guard.api.gitee_webhook import handle_webhook as handle_gitee_webhook
from pulse_guard.api.github_webhook import handle_webhook as handle_github_webhook
from pulse_guard.worker.tasks import process_pull_request

# 创建路由器
router = APIRouter()

# 包含分析路由
router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])


@router.post("/webhook/github")
async def github_webhook(request: Request):
    """GitHub Webhook 端点"""
    return await handle_github_webhook(request)


@router.post("/webhook/gitee")
async def gitee_webhook(request: Request):
    """Gitee Webhook 端点"""
    return await handle_gitee_webhook(request)


@router.post("/review")
async def manual_review(repo: str, pr_number: int, platform: str = "github"):
    """手动触发代码审查"""
    # 启动异步任务 - 手动触发时没有作者信息
    task = process_pull_request.delay(
        repo=repo,
        pr_number=pr_number,
        platform=platform,
        author_info=None
    )

    return {
        "status": "success",
        "message": f"Manual review started for PR #{pr_number} from {repo}",
        "task_id": task.id,
        "platform": platform,
    }


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}
