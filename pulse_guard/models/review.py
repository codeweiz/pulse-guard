"""
代码审查结果相关的数据模型。
"""
from enum import Enum
from typing import List, Optional, Dict

from pydantic import BaseModel


class SeverityLevel(str, Enum):
    """严重程度级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IssueCategory(str, Enum):
    """问题类别"""
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BEST_PRACTICES = "best_practices"
    DOCUMENTATION = "documentation"
    OTHER = "other"


class CodeIssue(BaseModel):
    """代码问题模型"""
    title: str
    description: str
    severity: SeverityLevel
    category: IssueCategory
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    suggestion: Optional[str] = None


class FileReview(BaseModel):
    """文件审查结果模型"""
    filename: str
    issues: List[CodeIssue] = []
    summary: str = ""

    @property
    def has_issues(self) -> bool:
        """是否有问题"""
        return len(self.issues) > 0

    @property
    def issue_count(self) -> Dict[SeverityLevel, int]:
        """按严重程度统计问题数量"""
        counts = {level: 0 for level in SeverityLevel}
        for issue in self.issues:
            counts[issue.severity] += 1
        return counts


class PRReview(BaseModel):
    """PR 审查结果模型"""
    pr_number: int
    repo_full_name: str
    file_reviews: List[FileReview] = []
    overall_summary: str = ""

    @property
    def total_issues(self) -> int:
        """总问题数"""
        return sum(len(review.issues) for review in self.file_reviews)

    @property
    def has_critical_issues(self) -> bool:
        """是否有严重问题"""
        for review in self.file_reviews:
            for issue in review.issues:
                if issue.severity == SeverityLevel.CRITICAL:
                    return True
        return False

    def format_comment(self) -> str:
        """格式化为 GitHub 评论"""
        comment = f"# 代码审查结果\n\n"

        # 添加总结
        comment += f"## 总体评价\n\n{self.overall_summary}\n\n"

        # 添加统计信息
        comment += f"共发现 **{self.total_issues}** 个问题，涉及 **{len(self.file_reviews)}** 个文件。\n\n"

        # 添加文件审查结果
        for file_review in self.file_reviews:
            comment += f"## 文件: `{file_review.filename}`\n\n"
            comment += f"{file_review.summary}\n\n"

            if file_review.has_issues:
                comment += "### 发现的问题\n\n"
                for issue in file_review.issues:
                    location = f"第 {issue.line_start}-{issue.line_end} 行" if issue.line_start else ""
                    severity_emoji = {
                        SeverityLevel.INFO: "ℹ️",
                        SeverityLevel.WARNING: "⚠️",
                        SeverityLevel.ERROR: "❌",
                        SeverityLevel.CRITICAL: "🚨"
                    }

                    comment += f"#### {severity_emoji[issue.severity]} {issue.title} ({issue.category.value})\n\n"
                    comment += f"{issue.description}\n\n"

                    if location:
                        comment += f"**位置**: {location}\n\n"

                    if issue.suggestion:
                        comment += f"**建议**: {issue.suggestion}\n\n"
            else:
                comment += "✅ 该文件没有发现问题\n\n"

        return comment
