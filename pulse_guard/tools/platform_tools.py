"""
统一的平台工具接口。

提供基于平台抽象层的 LangChain 工具，替代原有的平台特定工具。
"""
from typing import Dict, List, Any
from langchain.tools import tool

from pulse_guard.platforms import get_platform_provider


@tool
def get_pr_info(input: str) -> Dict[str, Any]:
    """获取 Pull Request 的基本信息
    
    Args:
        input: 输入格式："platform|owner/repo|pr_number"
        
    Returns:
        Pull Request 信息
    """
    # 解析输入
    parts = input.split('|')
    if len(parts) != 3:
        raise ValueError("Input format should be 'platform|owner/repo|pr_number'")

    platform, repo, pr_number_str = parts
    pr_number = int(pr_number_str)

    # 获取平台提供者并调用方法
    provider = get_platform_provider(platform)
    return provider.get_pr_info(repo, pr_number)


@tool
def get_pr_files(input: str) -> List[Dict[str, Any]]:
    """获取 Pull Request 修改的文件列表
    
    Args:
        input: 输入格式："platform|owner/repo|pr_number"
        
    Returns:
        文件列表
    """
    # 解析输入
    parts = input.split('|')
    if len(parts) != 3:
        raise ValueError("Input format should be 'platform|owner/repo|pr_number'")

    platform, repo, pr_number_str = parts
    pr_number = int(pr_number_str)

    # 获取平台提供者并调用方法
    provider = get_platform_provider(platform)
    return provider.get_pr_files(repo, pr_number)


@tool
def get_file_content(input: str) -> str:
    """获取文件内容
    
    Args:
        input: 输入格式："platform|owner/repo|file_path|ref"
        
    Returns:
        文件内容
    """
    # 解析输入
    parts = input.split('|')
    if len(parts) != 4:
        raise ValueError("Input format should be 'platform|owner/repo|file_path|ref'")

    platform, repo, file_path, ref = parts

    # 获取平台提供者并调用方法
    provider = get_platform_provider(platform)
    return provider.get_file_content(repo, file_path, ref)


@tool
def post_pr_comment(input: str) -> Dict[str, Any]:
    """发布 Pull Request 评论
    
    Args:
        input: 输入格式："platform|owner/repo|pr_number|comment"
        
    Returns:
        评论信息
    """
    # 解析输入
    parts = input.split('|', 3)  # 最多分成3次，因为评论内容可能包含|符号
    if len(parts) != 4:
        raise ValueError("Input format should be 'platform|owner/repo|pr_number|comment'")

    platform, repo, pr_number_str, comment = parts
    pr_number = int(pr_number_str)

    # 获取平台提供者并调用方法
    provider = get_platform_provider(platform)
    return provider.post_pr_comment(repo, pr_number, comment)
