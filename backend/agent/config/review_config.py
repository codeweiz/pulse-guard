"""代码审查配置"""
from dataclasses import dataclass


@dataclass
class ReviewConfig:
    """代码审查配置"""

    # 评分权重
    SCORE_WEIGHTS = {
        "code_quality": 0.25,
        "security": 0.25,
        "business": 0.25,
        "performance": 0.125,
        "best_practices": 0.125,
    }

    # 默认评分
    DEFAULT_SCORES = {
        "overall_score": 80,
        "code_quality_score": 80,
        "security_score": 80,
        "business_score": 80,
        "performance_score": 80,
        "best_practices_score": 80,
    }

    # 平台评论长度限制
    PLATFORM_COMMENT_LIMITS = {
        "github": 8000,
        "gitee": 3000,
        "default": 4000,
    }

    # 文件内容限制
    FILE_CONTENT_LIMITS = {
        "patch_max_length": 1500,
        "content_max_length": 3000,
        "response_max_length": 1000,
    }

    # 并发配置
    CONCURRENCY_CONFIG = {
        "max_concurrent_files": 10,
        "timeout_seconds": 300,
    }

    # 问题严重程度映射
    SEVERITY_ORDER = {
        "critical": 0,
        "error": 1,
        "warning": 2,
        "info": 3,
    }

    # 问题类别映射
    ISSUE_CATEGORIES = [
        "code_quality",
        "security",
        "performance",
        "best_practices",
        "documentation",
        "other"
    ]

    # 严重程度列表
    SEVERITY_LEVELS = ["info", "warning", "error", "critical"]


# 全局配置实例
review_config = ReviewConfig()
