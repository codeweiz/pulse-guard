"""
Gitee Webhook 处理模块。
"""
import logging
from typing import Any

from fastapi import Request
from starlette.responses import JSONResponse

from pulse_guard.worker.tasks import process_pull_request

# 配置日志
logger = logging.getLogger(__name__)


async def handle_webhook(request: Request) -> JSONResponse | dict[str, str | Any]:
    """处理 Gitee Webhook 请求

    Args:
        request: FastAPI 请求对象

    Returns:
        响应数据
    """
    # 记录请求头信息
    headers = dict(request.headers.items())
    event_type = headers.get("x-gitee-event")

    logger.info(f"Received Gitee webhook: event={event_type}")

    try:
        # 直接从请求中获取 JSON 数据
        event_body = await request.json()

        # 检查是否是 PR 事件
        if event_type != "Merge Request Hook":
            logger.info(f"非 PR 事件 (event_type={event_type}), 已忽略")
            return JSONResponse(content={"msg": "非 PR 事件，已忽略"}, status_code=200)

        # 提取 PR 信息
        pr_data = event_body.get("pull_request")
        repo_data = event_body.get("repository")
        action = event_body.get("action")

        if not pr_data or not repo_data:
            logger.info("缺少 PR 或仓库数据，已忽略")
            return JSONResponse(content={"msg": "缺少 PR 或仓库数据，已忽略"}, status_code=200)

        # 提取 PR 信息
        repo = repo_data["full_name"]
        pr_number = pr_data["number"]

        logger.info(f"处理 Gitee PR 事件: 仓库={repo}, PR 编号={pr_number}, 操作={action}")

        # 检查事件类型是否在 "open", "update", "reopen", "edit" 中
        if action in ["open", "update", "reopen", "edit"]:
            # 异步处理 PR
            task = process_pull_request.delay(repo=repo, pr_number=pr_number, platform="gitee")
            logger.info(f"Task created with ID: {task.id}")

            return {
                "status": "success",
                "message": f"仓库 {repo} 的 PR 编号{pr_number} 正在处理中",
                "event_type": event_type,
                "action": action,
                "task_id": task.id
            }
        else:
            logger.info(f"PR 操作 '{action}' 不受支持，已忽略")
            return {
                "status": "success",
                "message": f"PR action '{action}' not supported",
                "event_type": event_type,
                "action": action
            }
    except Exception as e:
        logger.error(f"执行 webhook 时出错: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": f"处理 webhook 时出错: {str(e)}"},
            status_code=500
        )
