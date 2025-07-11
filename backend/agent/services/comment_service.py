"""评论服务"""
import logging
from typing import Dict, List, Any, Union

from backend.models.review import CodeIssue, FileReview, IssueCategory, PRReview, SeverityLevel
from backend.models.workflow import AgentState, FileReviewInfo, EnhancedAnalysis, CodeIssueInfo
from backend.platforms import get_platform_provider
from backend.agent.config.review_config import review_config

logger = logging.getLogger(__name__)


class CommentService:
    """评论服务"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def post_review_comment(self, state: AgentState) -> AgentState:
        """发布审查评论并保存到数据库"""
        pr_info = state.pr_info
        platform = pr_info.platform
        file_reviews = state.file_reviews
        overall_summary = state.overall_summary
        enhanced_analysis = state.enhanced_analysis
        
        # 保存到数据库
        self._save_to_database(state)
        
        # 创建评论内容
        comment_text = self._create_comment_content(
            file_reviews, enhanced_analysis, overall_summary, state.pr_info
        )
        
        # 发布评论
        self._publish_comment(pr_info, platform, comment_text)
        
        return state
    
    def _save_to_database(self, state: AgentState) -> None:
        """保存审查结果到数据库"""
        try:
            from backend.database import DatabaseManager
            
            pr_info = state.pr_info
            file_reviews = state.file_reviews
            enhanced_analysis = state.enhanced_analysis
            
            db_record_id = DatabaseManager.save_complete_review_result(
                repo_full_name=pr_info.repo_full_name,
                pr_number=pr_info.number,
                pr_title=pr_info.title,
                pr_description=pr_info.body,
                pr_author=pr_info.author.login,
                platform=pr_info.platform,
                review_result={
                    "enhanced_analysis": enhanced_analysis.model_dump() if enhanced_analysis else None,
                    "file_reviews": [
                        fr.model_dump() if isinstance(fr, FileReviewInfo) else fr 
                        for fr in file_reviews
                    ],
                },
            )
            
            self.logger.info(f"审查结果已保存到数据库，记录ID: {db_record_id}")
            state.db_record_id = db_record_id
            
        except Exception as e:
            self.logger.error(f"保存审查结果到数据库失败: {e}")
    
    def _create_comment_content(
        self,
        file_reviews: List[FileReviewInfo],
        enhanced_analysis: EnhancedAnalysis,
        overall_summary: str,
        pr_info
    ) -> str:
        """创建评论内容"""
        comment_parts = []
        
        # 添加增强分析结果
        if enhanced_analysis:
            comment_parts.extend(self._format_enhanced_analysis(enhanced_analysis))
        
        # 创建PR审查结果
        pr_review = self._create_pr_review(file_reviews, overall_summary, pr_info)
        
        # 生成完整评论
        if comment_parts:
            comment_text = "\n".join(comment_parts)
            comment_text += "\n\n" + pr_review.format_comment()
        else:
            comment_text = pr_review.format_comment()
        
        return comment_text
    
    def _format_enhanced_analysis(self, enhanced_analysis: EnhancedAnalysis) -> List[str]:
        """格式化增强分析结果"""
        comment_parts = []
        
        comment_parts.append("# 🔍 代码审查报告")
        comment_parts.append("")
        comment_parts.append("## 📊 评分概览")
        comment_parts.append(f"- **总体评分**: {enhanced_analysis.overall_score:.1f}/100")
        comment_parts.append(f"- **业务逻辑**: {enhanced_analysis.business_score:.1f}/100")
        comment_parts.append(f"- **代码质量**: {enhanced_analysis.code_quality_score:.1f}/100")
        comment_parts.append(f"- **安全性**: {enhanced_analysis.security_score:.1f}/100")
        comment_parts.append(f"- **规范通过率**: {enhanced_analysis.standards_passed}/{enhanced_analysis.standards_total}")
        comment_parts.append("")
        comment_parts.append("## 📝 总体评价")
        comment_parts.append(enhanced_analysis.summary)
        comment_parts.append("")
        
        # 添加文件影响分析
        if enhanced_analysis.file_results:
            comment_parts.append("## 📁 文件影响分析")
            for file_result in enhanced_analysis.file_results:
                comment_parts.extend(self._format_file_analysis(file_result))
        
        return comment_parts
    
    def _format_file_analysis(self, file_result: FileReviewInfo) -> List[str]:
        """格式化单个文件分析"""
        impact_level = "medium"  # 默认值
        impact_emoji = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴",
        }.get(impact_level, "⚪")
        
        parts = []
        parts.append(f"### {impact_emoji} `{file_result.filename}`")
        parts.append(f"- **影响级别**: {impact_level}")
        parts.append(f"- **代码质量**: {file_result.code_quality_score:.1f}/100")
        parts.append(f"- **安全评分**: {file_result.security_score:.1f}/100")
        parts.append(f"- **问题数量**: {len(file_result.issues)}")
        parts.append(f"- **业务影响**: {file_result.summary}")
        parts.append("")
        
        return parts
    
    def _create_pr_review(
        self,
        file_reviews: List[FileReviewInfo],
        overall_summary: str,
        pr_info = None
    ) -> PRReview:
        """创建PR审查结果"""
        return PRReview(
            pr_number=pr_info.number if pr_info else 0,
            repo_full_name=pr_info.repo_full_name if pr_info else "",
            overall_summary=overall_summary or "代码审查完成",
            file_reviews=[
                FileReview(
                    filename=review.filename,
                    summary=review.summary,
                    issues=[
                        self._safe_create_code_issue(issue.model_dump() if isinstance(issue, CodeIssueInfo) else issue)
                        for issue in review.issues
                    ],
                )
                for review in file_reviews
            ],
        )
    
    def _safe_create_code_issue(self, issue_dict: Dict[str, Any]) -> CodeIssue:
        """安全地创建CodeIssue对象"""
        try:
            severity_str = issue_dict.get("severity", issue_dict.get("type", "info"))
            category_str = issue_dict.get("category", "other")
            
            # 转换为枚举值
            try:
                severity = SeverityLevel(severity_str.lower())
            except ValueError:
                severity = SeverityLevel.INFO
            
            try:
                category = IssueCategory(category_str.lower())
            except ValueError:
                category = IssueCategory.OTHER
            
            return CodeIssue(
                title=issue_dict.get("title", "未知问题"),
                description=issue_dict.get("description", ""),
                severity=severity,
                category=category,
                line_start=issue_dict.get("line", issue_dict.get("line_start")),
                line_end=issue_dict.get("line", issue_dict.get("line_end")),
                suggestion=issue_dict.get("suggestion", ""),
            )
        except Exception as e:
            self.logger.warning(f"创建CodeIssue失败: {e}")
            return CodeIssue(
                title=issue_dict.get("title", "解析失败的问题"),
                description=str(issue_dict),
                severity=SeverityLevel.INFO,
                category=IssueCategory.OTHER,
            )
    
    def _publish_comment(self, pr_info, platform: str, comment_text: str) -> None:
        """发布评论"""
        provider = get_platform_provider(platform)
        
        try:
            # 获取平台特定的长度限制
            max_length = review_config.PLATFORM_COMMENT_LIMITS.get(
                platform, 
                review_config.PLATFORM_COMMENT_LIMITS["default"]
            )
            
            # 使用分批评论功能
            results = provider.post_pr_comments_batch(
                pr_info.repo_full_name,
                pr_info.number,
                comment_text,
                max_length=max_length,
            )
            
            # 统计发布结果
            success_count = sum(1 for r in results if "error" not in r)
            total_count = len(results)
            
            if success_count == total_count:
                print(f"✅ 已发布审查评论到 PR #{pr_info.number} (共 {total_count} 条)")
            else:
                print(f"⚠️ 部分评论发布成功: {success_count}/{total_count} 条到 PR #{pr_info.number}")
                
        except Exception as e:
            print(f"❌ 发布评论失败: {str(e)}")
            # 尝试发布简化版本
            self._publish_fallback_comment(provider, pr_info, comment_text)
    
    def _publish_fallback_comment(self, provider, pr_info, original_comment: str) -> None:
        """发布简化的备用评论"""
        try:
            simplified_comment = self._create_fallback_comment()
            provider.post_pr_comment(
                pr_info.repo_full_name, 
                pr_info.number, 
                simplified_comment
            )
            print(f"✅ 已发布简化评论到 PR #{pr_info.number}")
        except Exception as fallback_error:
            print(f"❌ 简化评论也发布失败: {str(fallback_error)}")
    
    def _create_fallback_comment(self) -> str:
        """创建极简的备用评论"""
        return """# 🔍 代码审查完成

📊 代码审查已完成，详细报告请查看完整分析或联系管理员

💡 详细报告请查看完整分析或联系管理员"""


# 全局评论服务实例
comment_service = CommentService()
