"""
平台抽象层模块。

提供统一的平台接口抽象，支持 GitHub、Gitee 等多个代码托管平台。
"""

from .base import PlatformProvider
from .factory import PlatformFactory, get_platform_provider
from .gitee_provider import GiteeProvider

# 导入所有平台提供者以触发自动注册
from .github_provider import GitHubProvider

# from .gitlab_provider import GitLabProvider  # 示例平台，暂时注释

__all__ = [
    "PlatformProvider",
    "PlatformFactory",
    "get_platform_provider",
    "GitHubProvider",
    "GiteeProvider",
    # "GitLabProvider",  # 示例平台，暂时注释
]
