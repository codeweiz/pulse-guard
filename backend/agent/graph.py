"""
代码审查工作流图 - 重构版本

这个文件现在作为新架构的入口点，主要功能已经重构到各个服务类中。
保持向后兼容性，同时提供更好的代码组织结构。
"""
import logging
from typing import Any, Dict

from backend.agent.core.workflow import code_review_workflow
from backend.agent.services.comment_service import comment_service
from backend.agent.services.pr_service import pr_service
from backend.agent.services.review_service import review_service

# 配置日志
logger = logging.getLogger(__name__)


# 向后兼容的包装函数
def fetch_pr_and_code_files(state):
    """获取PR信息和代码文件内容 - 向后兼容包装器"""
    return pr_service.fetch_pr_and_code_files(state)


async def intelligent_code_review(state):
    """智能代码审查 - 向后兼容包装器"""
    return await review_service.intelligent_code_review(state)


def generate_summary(state):
    """生成总体评价 - 向后兼容包装器"""
    # 这个功能现在集成在review_service中，这里保持向后兼容
    return state


def post_review_comment(state):
    """发布审查评论并保存到数据库 - 向后兼容包装器"""
    return comment_service.post_review_comment(state)


# 构建LangGraph工作流图
def build_code_review_graph():
    """构建代码审查LangGraph - 使用新架构"""
    return code_review_workflow.build_graph()


# 主要的运行函数
async def run_code_review_async(pr_info: Dict[str, Any]) -> Dict[str, Any]:
    """异步运行代码审查 - 使用新架构"""
    return await code_review_workflow.run_async(pr_info)


def run_code_review(pr_info: Dict[str, Any]) -> Dict[str, Any]:
    """运行代码审查 - 同步包装器，使用新架构"""
    return code_review_workflow.run_sync(pr_info)
