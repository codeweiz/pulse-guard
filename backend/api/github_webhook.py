"""
GitHub Webhook 处理模块。
"""

import logging
from typing import Any

from fastapi import Request
from starlette.responses import JSONResponse

from backend.models.workflow import UserInfo, WorkflowInput
from backend.worker.tasks import process_pull_request

# 配置日志
logger = logging.getLogger(__name__)


async def handle_webhook(
    request: Request,
) -> JSONResponse | dict[str, str | None | Any]:
    """处理 GitHub Webhook 请求

    Args:
        request: FastAPI 请求对象

    Returns:
        响应数据
    """
    # 记录请求头信息
    headers = dict(request.headers.items())
    event_type = headers.get("x-github-event")
    delivery_id = headers.get("x-github-delivery")

    logger.info(f"Received GitHub webhook: event={event_type}, delivery={delivery_id}")
    logger.debug(f"All request headers: {headers}")

    try:
        # 直接从请求中获取 JSON 数据
        event_body = await request.json()
        logger.debug(f"Webhook payload received, size: {len(str(event_body))} chars")

        # 检查是否是 PR 事件
        pr_data = event_body.get("pull_request")
        repo_data = event_body.get("repository")
        action = event_body.get("action")

        if not pr_data or not repo_data:
            logger.info("Not a PR event, ignoring")
            return JSONResponse(content={"msg": "非 PR 事件，已忽略"}, status_code=200)

        # 提取基本信息
        repo = repo_data["full_name"]  # owner/repo
        pr_number = pr_data["number"]

        # 提取作者信息 - GitHub的作者信息在pr_data的user字段
        author_data = pr_data.get("user", {})

        # 创建作者信息模型
        try:
            author_info = UserInfo(
                login=author_data.get("login", "unknown"),
                id=str(author_data.get("id", "")),
                name=author_data.get("name", author_data.get("login", "")),
                email=author_data.get("email", ""),
                type=author_data.get("type", "User"),
                avatar_url=author_data.get("avatar_url", "")
            )
        except Exception as e:
            logger.warning(f"解析作者信息失败: {e}, 使用默认值")
            author_info = UserInfo(login="unknown")

        logger.info(
            f"Processing PR event: repo={repo}, pr_number={pr_number}, action={action}, author={author_info.login}"
        )

        # 检查是否是我们关心的事件类型
        if action in ["opened", "synchronize", "reopened", "edited"]:
            # 创建工作流输入
            workflow_input = WorkflowInput(
                repo=repo,
                number=pr_number,
                platform="github",
                author=author_info
            )

            # 异步处理 PR - 传递完整的工作流输入
            task = process_pull_request.delay(
                repo=repo,
                pr_number=pr_number,
                platform="github",
                author_info=author_info.model_dump()  # 序列化作者信息
            )
            logger.info(f"Task created with ID: {task.id}")

            return {
                "status": "success",
                "message": f"Processing PR #{pr_number} from {repo}",
                "event_type": event_type,
                "action": action,
                "task_id": task.id,
                "author": author_info.login,
            }
        else:
            logger.info(f"PR action '{action}' not supported, ignoring")
            return {
                "status": "success",
                "message": f"PR action '{action}' not supported",
                "event_type": event_type,
                "action": action,
            }

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JSONResponse(
            content={
                "status": "error",
                "message": f"Error processing webhook: {str(e)}",
                "headers": headers,
            },
            status_code=500,
        )
