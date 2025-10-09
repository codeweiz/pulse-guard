"""
Gitee Webhook 处理模块。
"""

import logging
from typing import Any

from fastapi import Request
from starlette.responses import JSONResponse

from backend.models.workflow import UserInfo, WorkflowInput
from backend.worker.tasks import process_pull_request

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
            return JSONResponse(
                content={"msg": "缺少 PR 或仓库数据，已忽略"}, status_code=200
            )

        # 提取基本信息
        repo = repo_data["full_name"]
        pr_number = pr_data["number"]

        # 提取作者信息 - Gitee的作者信息在event_body的author字段
        author_data = event_body.get("author", {})
        if not author_data and pr_data.get("user"):
            # 如果event_body中没有author，尝试从pr_data的user字段获取
            author_data = pr_data.get("user", {})

        # 创建作者信息模型
        try:
            author_info = UserInfo(
                login=author_data.get("login", author_data.get("name", "unknown")),
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
            f"处理 Gitee PR 事件: 仓库={repo}, PR 编号={pr_number}, 操作={action}, 作者={author_info.login}"
        )

        # 检查事件类型是否在 "open", "update", "reopen", "edit" 中
        if action in ["open", "update", "reopen", "edit"]:
            # 创建工作流输入
            workflow_input = WorkflowInput(
                repo=repo,
                number=pr_number,
                platform="gitee",
                author=author_info
            )

            # 异步处理 PR - 传递完整的工作流输入
            task = process_pull_request.delay(
                repo=repo,
                pr_number=pr_number,
                platform="gitee",
                author_info=author_info.model_dump()
            )
            logger.info(f"Task created with ID: {task.id}")

            return {
                "status": "success",
                "message": f"仓库 {repo} 的 PR 编号{pr_number} 正在处理中",
                "event_type": event_type,
                "action": action,
                "task_id": task.id,
                "author": author_info.login,
            }
        else:
            logger.info(f"PR 操作 '{action}' 不受支持，已忽略")
            return {
                "status": "success",
                "message": f"PR action '{action}' not supported",
                "event_type": event_type,
                "action": action,
            }
    except Exception as e:
        logger.error(f"执行 webhook 时出错: {str(e)}")
        return JSONResponse(
            content={"status": "error", "message": f"处理 webhook 时出错: {str(e)}"},
            status_code=500,
        )
