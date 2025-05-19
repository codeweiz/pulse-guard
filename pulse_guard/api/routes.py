"""
API 路由定义模块。
"""
from fastapi import APIRouter, Request, Depends, HTTPException

from pulse_guard.api.webhook import handle_webhook
from pulse_guard.worker.tasks import process_pull_request

# 创建路由器
router = APIRouter()


@router.post("/webhook/github")
async def github_webhook(request: Request):
    """GitHub Webhook 端点"""
    return await handle_webhook(request)


@router.post("/review")
async def manual_review(repo: str, pr_number: int):
    """手动触发代码审查"""
    # 启动异步任务
    task = process_pull_request.delay(repo=repo, pr_number=pr_number)
    
    return {
        "status": "success",
        "message": f"Processing PR #{pr_number} from {repo}",
        "task_id": task.id
    }


@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}
