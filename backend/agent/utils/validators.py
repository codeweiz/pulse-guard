"""数据验证工具"""
import logging
from typing import Any, Dict, Union

from backend.agent.config.review_config import review_config
from backend.models.workflow import FileInfo, PRInfo

logger = logging.getLogger(__name__)


class DataValidator:
    """数据验证器"""

    @staticmethod
    def safe_get_score(score: Any) -> int:
        """安全地获取评分"""
        try:
            if isinstance(score, (int, float)):
                return max(0, min(100, int(score)))
            elif isinstance(score, str):
                return max(0, min(100, int(float(score))))
            else:
                return review_config.DEFAULT_SCORES["overall_score"]
        except (ValueError, TypeError):
            return review_config.DEFAULT_SCORES["overall_score"]

    @staticmethod
    def safe_get_string(data: Any, default: str = "") -> str:
        """安全地获取字符串值"""
        if data is None:
            return default
        return str(data)

    @staticmethod
    def safe_get_user_login(pr_info: Union[PRInfo, Dict[str, Any]]) -> str:
        """安全地获取用户登录名"""
        try:
            if isinstance(pr_info, PRInfo):
                return pr_info.author.login
            elif isinstance(pr_info, dict):
                user = pr_info.get("user", "")
                if isinstance(user, dict):
                    return str(user.get("login", "unknown"))
                elif isinstance(user, str):
                    return user
                else:
                    return "unknown"
            else:
                return "unknown"
        except Exception as e:
            logger.warning(f"获取用户登录名失败: {e}")
            return "unknown"

    @staticmethod
    def validate_file_info(file_data: Dict[str, Any]) -> FileInfo:
        """验证并创建FileInfo对象"""
        try:
            return FileInfo(**file_data)
        except Exception as e:
            logger.warning(f"跳过无效文件数据: {e}")
            raise

    @staticmethod
    def validate_issue_data(issue_dict: Dict[str, Any]) -> Dict[str, Any]:
        """验证和修复问题数据"""
        validated_issue = {
            "type": issue_dict.get("type", "info"),
            "title": issue_dict.get("title", "未知问题"),
            "description": issue_dict.get("description", ""),
            "line": issue_dict.get("line", issue_dict.get("line_start")),
            "suggestion": issue_dict.get("suggestion", ""),
            "severity": issue_dict.get("severity", issue_dict.get("type", "info")),
            "category": issue_dict.get("category", "other"),
        }

        # 验证严重程度和类别
        if validated_issue["severity"] not in review_config.SEVERITY_LEVELS:
            validated_issue["severity"] = "info"

        if validated_issue["category"] not in review_config.ISSUE_CATEGORIES:
            validated_issue["category"] = "other"

        return validated_issue

    @staticmethod
    def create_default_file_review(filename: str, error_msg: str = "") -> Dict[str, Any]:
        """创建默认的文件审查结果"""
        return {
            "filename": filename,
            "score": 70,
            "code_quality_score": 70,
            "security_score": 70,
            "business_score": 70,
            "performance_score": 70,
            "best_practices_score": 70,
            "issues": [
                {
                    "type": "warning",
                    "title": "审查异常" if error_msg else "默认结果",
                    "description": error_msg or "使用默认审查结果",
                    "severity": "warning",
                    "category": "other",
                    "suggestion": "请检查审查过程",
                }
            ],
            "positive_points": ["文件已审查"],
            "summary": f"文件 {filename} 审查完成" + (f"（{error_msg}）" if error_msg else ""),
        }


# 全局验证器实例
validator = DataValidator()
