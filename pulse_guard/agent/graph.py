import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from langgraph.graph import END, StateGraph
from pulse_guard.llm.client import get_llm
from pulse_guard.models.review import (
    CodeIssue,
    FileReview,
    IssueCategory,
    PRReview,
    SeverityLevel,
)
from pulse_guard.models.workflow import (
    AgentState,
    CodeIssueInfo,
    EnhancedAnalysis,
    FileInfo,
    FileReviewInfo,
    PRInfo,
    UserInfo,
)
from pulse_guard.platforms import get_platform_provider
from pulse_guard.utils.file_type_utils import is_code_file

# 配置日志
logger = logging.getLogger(__name__)


def fetch_pr_and_code_files(state: AgentState) -> AgentState:
    """获取PR信息和代码文件内容"""
    pr_info = state.pr_info
    platform = pr_info.platform

    # 获取平台提供者
    provider = get_platform_provider(platform)

    # 获取 PR 详细信息
    pr_details = provider.get_pr_info(pr_info.repo, pr_info.number)

    # 从 pr_details 中移除可能冲突的字段
    safe_pr_details = {k: v for k, v in pr_details.items()
                       if k not in ['repo', 'number', 'platform', 'author']}

    updated_pr_info = PRInfo(
        repo=pr_info.repo,
        number=pr_info.number,
        platform=pr_info.platform,
        author=pr_info.author,
        **safe_pr_details
    )

    # 获取 PR 修改的文件列表
    all_files = provider.get_pr_files(pr_info.repo, pr_info.number)

    # 转换为 FileInfo 模型
    file_infos = []
    for file_data in all_files:
        try:
            file_info = FileInfo(**file_data)
            file_infos.append(file_info)
        except Exception as e:
            logger.warning(f"跳过无效文件数据: {e}")
            continue

    # 过滤出代码文件
    code_files = [f for f in file_infos if is_code_file(f.filename)]

    logger.info(
        f"总文件数: {len(all_files)}, 有效文件数: {len(file_infos)}, 代码文件数: {len(code_files)}"
    )

    # 获取所有代码文件的内容
    file_contents = {}
    enhanced_files = []

    for file in code_files:
        if file.status != "removed":
            try:
                content = provider.get_file_content(
                    updated_pr_info.repo_full_name,
                    file.filename,
                    updated_pr_info.head_sha,
                )
                file_contents[file.filename] = content
                # 更新文件内容
                file.content = content
            except Exception as e:
                # 如果获取文件内容失败，记录错误
                error_msg = f"Error fetching file content: {str(e)}"
                file_contents[file.filename] = error_msg
                file.content = error_msg
                logger.warning(f"获取文件内容失败 {file.filename}: {e}")

        enhanced_files.append(file)

    # 更新状态
    new_state = state.model_copy()
    new_state.pr_info = updated_pr_info
    new_state.files = enhanced_files
    new_state.file_contents = file_contents
    new_state.current_file_index = 0
    new_state.file_reviews = []

    return new_state


async def intelligent_code_review(state: AgentState) -> AgentState:
    """智能代码审查"""
    pr_info = state.pr_info
    files = state.files

    if not files:
        logger.warning("没有代码文件需要审查")
        new_state = state.model_copy()
        new_state.file_reviews = []
        new_state.overall_summary = "没有代码文件需要审查"
        new_state.enhanced_analysis = EnhancedAnalysis(
            overall_score=100,
            code_quality_score=100,
            security_score=100,
            business_score=100,
            file_results=[],
            summary="没有代码文件需要审查",
        )
        return new_state

    logger.info(f"开始并发审查 {len(files)} 个代码文件")

    # 并发审查每个文件
    file_reviews = []
    try:
        logger.info(f"使用 asyncio.gather 并发处理 {len(files)} 个文件")

        # 创建所有文件审查任务
        tasks = []
        for file in files:
            task = _review_single_file_async(file, pr_info)
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for i, (file, result) in enumerate(zip(files, results)):
            if isinstance(result, Exception):
                logger.error(f"文件 {file.filename} 审查异常: {result}")
                # 添加失败的默认结果
                file_review = FileReviewInfo(
                    filename=file.filename,
                    score=70,
                    issues=[
                        CodeIssueInfo(
                            type="error",
                            title="审查失败",
                            description=str(result),
                        )
                    ],
                    positive_points=[],
                    summary=f"审查失败: {str(result)}",
                )
                file_reviews.append(file_review)
            else:
                # 将字典结果转换为FileReviewInfo模型
                if isinstance(result, dict):
                    issues = []
                    for issue_data in result.get("issues", []):
                        try:
                            issue = CodeIssueInfo(**issue_data)
                            issues.append(issue)
                        except Exception as e:
                            logger.warning(f"转换问题信息失败: {e}")
                            continue

                    file_review = FileReviewInfo(
                        filename=result.get("filename", file.filename),
                        score=result.get("score", 80),
                        code_quality_score=result.get("code_quality_score", 80),
                        security_score=result.get("security_score", 80),
                        business_score=result.get("business_score", 80),
                        performance_score=result.get("performance_score", 80),
                        best_practices_score=result.get("best_practices_score", 80),
                        issues=issues,
                        positive_points=result.get("positive_points", []),
                        summary=result.get("summary", ""),
                    )
                    file_reviews.append(file_review)
                else:
                    # 如果result不是字典，创建一个默认的FileReviewInfo
                    logger.warning(f"意外的结果类型: {type(result)}, 创建默认审查结果")
                    file_review = FileReviewInfo(
                        filename=file.filename,
                        score=70,
                        issues=[
                            CodeIssueInfo(
                                type="warning",
                                title="审查结果解析异常",
                                description=f"无法解析审查结果: {str(result)}",
                            )
                        ],
                        positive_points=[],
                        summary="审查结果解析异常",
                    )
                    file_reviews.append(file_review)
                logger.info(f"文件 {file.filename} 审查完成")

        # 计算总体评分
        overall_result = _calculate_overall_scores(
            [fr.model_dump() if isinstance(fr, FileReviewInfo) else fr for fr in file_reviews])

        logger.info(f"并发审查完成，总体评分: {overall_result['overall_score']}")

        # 创建增强分析结果
        enhanced_analysis = EnhancedAnalysis(
            overall_score=overall_result.get("overall_score", 80),
            code_quality_score=overall_result.get("code_quality_score", 80),
            security_score=overall_result.get("security_score", 80),
            business_score=overall_result.get("business_score", 80),
            file_results=file_reviews,
            summary=overall_result.get("summary", "并发审查完成"),
            standards_passed=overall_result.get("standards_passed", 0),
            standards_failed=overall_result.get("standards_failed", 0),
            standards_total=overall_result.get("standards_total", 0),
        )

        # 更新状态
        new_state = state.model_copy()
        new_state.file_reviews = file_reviews
        new_state.overall_summary = overall_result.get("summary", "并发审查完成")
        new_state.enhanced_analysis = enhanced_analysis

        return new_state

    except Exception as e:
        logger.error(f"并发审查失败: {e}")
        # 降级到简单审查
        return state


def generate_summary(state: AgentState) -> AgentState:
    """生成总体评价"""
    file_reviews = state.file_reviews
    enhanced_analysis = state.enhanced_analysis

    # 如果有增强分析结果，优先使用
    if enhanced_analysis:
        new_state = state.model_copy()
        new_state.overall_summary = enhanced_analysis.summary
        return new_state

    # 如果没有文件审查结果，返回默认总结
    if not file_reviews:
        new_state = state.model_copy()
        new_state.overall_summary = "没有找到需要审查的文件。"
        return new_state

    # 构建文件审查摘要
    file_reviews_text = ""
    for review in file_reviews:
        if isinstance(review, FileReviewInfo):
            filename = review.filename
            summary = review.summary
            issues_count = len(review.issues)

            file_reviews_text += f"## {filename}\n"
            file_reviews_text += f"- 摘要: {summary}\n"
            file_reviews_text += f"- 问题数: {issues_count}\n"

            if issues_count > 0:
                file_reviews_text += "- 问题列表:\n"
                for issue in review.issues:
                    file_reviews_text += f"  - [{issue.severity}] {issue.title}\n"
        else:
            # 向后兼容字典格式
            filename = review.get("filename", "unknown")
            summary = review.get("summary", "")
            issues_count = len(review.get("issues", []))

            file_reviews_text += f"## {filename}\n"
            file_reviews_text += f"- 摘要: {summary}\n"
            file_reviews_text += f"- 问题数: {issues_count}\n"

            if issues_count > 0:
                file_reviews_text += "- 问题列表:\n"
                for issue in review.get("issues", []):
                    severity = issue.get("severity", "medium") if isinstance(issue, dict) else getattr(issue,
                                                                                                       "severity",
                                                                                                       "medium")
                    title = issue.get("title", "") if isinstance(issue, dict) else getattr(issue, "title", "")
                    file_reviews_text += f"  - [{severity}] {title}\n"

        file_reviews_text += "\n"

    # 使用 LLM 生成总体评价
    llm = get_llm()

    prompt = f"""
请根据以下各文件的代码审查结果，生成一个总体评价:

{file_reviews_text}

请在总结中包括:
1. PR 的整体质量评价，从 0 到 10 分给 PR 评分
2. 主要问题和模式
3. 关键改进建议
4. 积极的反馈和鼓励

你的总结将作为 PR 评论的开头部分，应该友好、专业且有建设性。

请使用中文回复。
"""

    # 获取 LLM 响应
    response = llm.invoke(prompt)
    overall_summary = str(response.content if hasattr(response, 'content') else response)

    # 更新状态
    new_state = state.model_copy()
    new_state.overall_summary = overall_summary
    return new_state


def post_review_comment(state: AgentState) -> AgentState:
    """发布审查评论并保存到数据库"""
    pr_info = state.pr_info
    platform = pr_info.platform
    file_reviews = state.file_reviews
    overall_summary = state.overall_summary
    enhanced_analysis = state.enhanced_analysis

    # 首先保存审查结果到数据库
    try:
        from pulse_guard.database import DatabaseManager

        db_record_id = DatabaseManager.save_complete_review_result(
            repo_full_name=pr_info.repo_full_name,
            pr_number=pr_info.number,
            pr_title=pr_info.title,
            pr_description=pr_info.body,
            pr_author=pr_info.author.login,
            platform=platform,
            review_result={
                "enhanced_analysis": enhanced_analysis.model_dump() if enhanced_analysis else None,
                "file_reviews": [fr.model_dump() if isinstance(fr, FileReviewInfo) else fr for fr in file_reviews],
            },
        )
        logger.info(f"审查结果已保存到数据库，记录ID: {db_record_id}")

        # 更新状态中的数据库记录ID
        state.db_record_id = db_record_id

    except Exception as e:
        logger.error(f"保存审查结果到数据库失败: {e}")
        # 继续执行，不因为数据库保存失败而中断评论发布

    # 创建增强的评论内容
    comment_parts = []

    # 添加增强分析结果
    if enhanced_analysis:
        # 处理Pydantic对象或字典格式
        if isinstance(enhanced_analysis, EnhancedAnalysis):
            overall_score = enhanced_analysis.overall_score
            business_score = enhanced_analysis.business_score
            code_quality_score = enhanced_analysis.code_quality_score
            security_score = enhanced_analysis.security_score
            standards_passed = enhanced_analysis.standards_passed
            standards_total = enhanced_analysis.standards_total
            summary = enhanced_analysis.summary
            file_results = enhanced_analysis.file_results
        else:
            # 向后兼容字典格式
            overall_score = enhanced_analysis.get("overall_score", 80)
            business_score = enhanced_analysis.get("business_score", 80)
            code_quality_score = enhanced_analysis.get("code_quality_score", 80)
            security_score = enhanced_analysis.get("security_score", 80)
            standards_passed = enhanced_analysis.get("standards_passed", 0)
            standards_total = enhanced_analysis.get("standards_total", 0)
            summary = enhanced_analysis.get("summary", "")
            file_results = enhanced_analysis.get("file_results", [])

        comment_parts.append("# 🔍 代码审查报告")
        comment_parts.append("")
        comment_parts.append("## 📊 评分概览")
        comment_parts.append(f"- **总体评分**: {overall_score:.1f}/100")
        comment_parts.append(f"- **业务逻辑**: {business_score:.1f}/100")
        comment_parts.append(f"- **代码质量**: {code_quality_score:.1f}/100")
        comment_parts.append(f"- **安全性**: {security_score:.1f}/100")
        comment_parts.append(f"- **规范通过率**: {standards_passed}/{standards_total}")
        comment_parts.append("")
        comment_parts.append("## 📝 总体评价")
        comment_parts.append(summary)
        comment_parts.append("")

        # 添加文件影响分析
        if file_results:
            comment_parts.append("## 📁 文件影响分析")
            for fa in file_results:
                # 处理FileReviewInfo对象或字典格式
                if isinstance(fa, FileReviewInfo):
                    filename = fa.filename
                    code_quality_score = fa.code_quality_score
                    security_score = fa.security_score
                    issues_count = len(fa.issues)
                    summary = fa.summary
                    impact_level = "medium"  # 默认值，FileReviewInfo没有impact_level字段
                else:
                    # 向后兼容字典格式
                    filename = fa.get("filename", "unknown")
                    code_quality_score = fa.get("code_quality_score", 80)
                    security_score = fa.get("security_score", 80)
                    issues_count = len(fa.get("issues", []))
                    summary = fa.get("summary", fa.get("business_impact", "无特殊影响"))
                    impact_level = fa.get("impact_level", fa.get("type", "medium"))

                impact_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴",
                }.get(impact_level, "⚪")

                comment_parts.append(f"### {impact_emoji} `{filename}`")
                comment_parts.append(f"- **影响级别**: {impact_level}")
                comment_parts.append(f"- **代码质量**: {code_quality_score:.1f}/100")
                comment_parts.append(f"- **安全评分**: {security_score:.1f}/100")
                comment_parts.append(f"- **问题数量**: {issues_count}")
                comment_parts.append(f"- **业务影响**: {summary}")
                comment_parts.append("")

    # 创建 PR 审查结果 - 安全地创建 CodeIssue 对象
    def _safe_create_code_issue(issue_dict: Dict[str, Any]) -> CodeIssue:
        """安全地创建 CodeIssue 对象"""
        try:
            # 确保必需字段存在
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
            logger.warning(f"创建 CodeIssue 失败: {e}, 使用默认值")
            return CodeIssue(
                title=issue_dict.get("title", "解析失败的问题"),
                description=str(issue_dict),
                severity=SeverityLevel.INFO,
                category=IssueCategory.OTHER,
            )

    pr_review = PRReview(
        pr_number=pr_info.number,
        repo_full_name=pr_info.repo_full_name,
        overall_summary=overall_summary or "代码审查完成",
        file_reviews=[
            FileReview(
                filename=review.filename if isinstance(review, FileReviewInfo) else review.get("filename", ""),
                summary=review.summary if isinstance(review, FileReviewInfo) else review.get("summary", ""),
                issues=[
                    _safe_create_code_issue(issue.model_dump() if isinstance(issue, CodeIssueInfo) else issue)
                    for issue in (review.issues if isinstance(review, FileReviewInfo) else review.get("issues", []))
                ],
            )
            for review in file_reviews
        ],
    )

    # 生成完整的评论内容（现在可以分批发送）
    if comment_parts:
        comment_text = "\n".join(comment_parts)
        # 添加完整的详细审查结果
        comment_text += "\n\n" + pr_review.format_comment()
    else:
        comment_text = pr_review.format_comment()

    # 获取平台提供者并发布评论
    provider = get_platform_provider(platform)

    try:
        # 使用分批评论功能，根据平台设置不同的长度限制
        max_length = 4000  # 默认限制
        if platform == "gitee":
            max_length = 3000  # Gitee 可能限制更严格
        elif platform == "github":
            max_length = 8000  # GitHub 限制相对宽松

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
            print(
                f"⚠️ 部分评论发布成功: {success_count}/{total_count} 条到 PR #{pr_info.number}"
            )

    except Exception as e:
        print(f"❌ 发布评论失败: {str(e)}")
        # 如果分批发布失败，尝试发布简化版本
        try:
            simplified_comment = _create_fallback_comment(
                file_reviews, enhanced_analysis  # type: ignore
            )
            provider.post_pr_comment(
                pr_info.repo_full_name, pr_info.number, simplified_comment
            )
            print(f"✅ 已发布简化评论到 PR #{pr_info.number}")
        except Exception as fallback_error:
            print(f"❌ 简化评论也发布失败: {str(fallback_error)}")

    # 更新状态
    return state


def _format_simplified_comment(
        pr_review: PRReview, file_reviews: List[Dict[str, Any]]
) -> str:
    """格式化简化的评论内容，减少长度"""
    comment_parts = []

    # 添加简化的总体评价
    if pr_review.overall_summary:
        comment_parts.append("## 📋 审查总结")
        # 限制总结长度
        summary = pr_review.overall_summary
        if len(summary) > 500:
            summary = summary[:500] + "..."
        comment_parts.append(summary)
        comment_parts.append("")

    # 添加统计信息
    total_issues = sum(len(review.get("issues", [])) for review in file_reviews)
    critical_issues = sum(
        1
        for review in file_reviews
        for issue in review.get("issues", [])
        if issue.get("severity") == "critical"
    )

    comment_parts.append("## 📊 审查统计")
    comment_parts.append(f"- 📁 审查文件: **{len(file_reviews)}** 个")
    comment_parts.append(f"- 🔍 发现问题: **{total_issues}** 个")
    if critical_issues > 0:
        comment_parts.append(f"- 🚨 严重问题: **{critical_issues}** 个")
    comment_parts.append("")

    # 只显示有问题的文件，并限制显示数量
    files_with_issues = [review for review in file_reviews if review.get("issues")]
    if files_with_issues:
        comment_parts.append("## ⚠️ 需要关注的文件")

        # 最多显示5个有问题的文件
        for review in files_with_issues[:5]:
            filename = review["filename"]
            issues = review.get("issues", [])
            issue_count = len(issues)

            # 统计问题严重程度
            critical_count = sum(
                1 for issue in issues if issue.get("severity") == "critical"
            )
            error_count = sum(1 for issue in issues if issue.get("severity") == "error")

            severity_info = []
            if critical_count > 0:
                severity_info.append(f"🚨{critical_count}")
            if error_count > 0:
                severity_info.append(f"❌{error_count}")

            severity_text = f" ({', '.join(severity_info)})" if severity_info else ""

            comment_parts.append(f"### `{filename}`")
            comment_parts.append(f"- 问题数量: **{issue_count}**{severity_text}")

            # 只显示最严重的问题
            if issues:
                # 按严重程度排序
                severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
                sorted_issues = sorted(
                    issues,
                    key=lambda x: severity_order.get(x.get("severity", "info"), 3),
                )

                top_issue = sorted_issues[0]
                comment_parts.append(
                    f"- 主要问题: {top_issue.get('title', '未知问题')}"
                )

            comment_parts.append("")

        # 如果有更多文件，显示提示
        if len(files_with_issues) > 5:
            remaining = len(files_with_issues) - 5
            comment_parts.append(
                f"*还有 {remaining} 个文件存在问题，详情请查看完整报告*"
            )
            comment_parts.append("")

    # 添加简化的建议
    comment_parts.append("## 💡 改进建议")
    if critical_issues > 0:
        comment_parts.append("- 🚨 请优先修复严重问题")
    if total_issues > 10:
        comment_parts.append("- 📝 建议分批修复问题，避免一次性修改过多")
    comment_parts.append("- 🔍 详细分析报告可通过 API 接口获取")

    return "\n".join(comment_parts)


def _create_fallback_comment(
        file_reviews: List[Union[FileReviewInfo, Dict[str, Any]]],
        enhanced_analysis: Optional[Union[EnhancedAnalysis, Dict[str, Any]]] = None
) -> str:
    """创建极简的备用评论，确保能够发布"""
    parts = []

    # 基本统计
    total_files = len(file_reviews)
    total_issues = 0
    critical_issues = 0

    for review in file_reviews:
        if isinstance(review, FileReviewInfo):
            total_issues += len(review.issues)
            critical_issues += sum(1 for issue in review.issues if issue.severity == "critical")
        else:
            # 向后兼容字典格式
            total_issues += len(review.get("issues", []))
            critical_issues += sum(
                1 for issue in review.get("issues", [])
                if issue.get("severity") == "critical"
            )

    parts.append("# 🔍 代码审查完成")
    parts.append("")
    parts.append(f"📊 **统计**: {total_files} 个文件，{total_issues} 个问题")

    if critical_issues > 0:
        parts.append(f"🚨 **严重问题**: {critical_issues} 个，请优先处理")

    if enhanced_analysis:
        if isinstance(enhanced_analysis, EnhancedAnalysis):
            score = enhanced_analysis.overall_score
        else:
            score = enhanced_analysis.get("overall_score", 80)
        parts.append(f"📈 **总体评分**: {score:.1f}/100")

    parts.append("")
    parts.append("💡 详细报告请查看完整分析或联系管理员")

    return "\n".join(parts)


# 构建 LangGraph
def build_code_review_graph() -> Any:
    """构建简化的代码审查 LangGraph"""
    # 创建图 - 使用 AgentState 而不是 LangGraphState 以保持类型一致性
    workflow = StateGraph(AgentState)

    # 添加节点 - 简化的流程
    workflow.add_node("fetch_pr_and_code_files", fetch_pr_and_code_files)
    workflow.add_node("intelligent_code_review", intelligent_code_review)
    workflow.add_node("post_review_comment", post_review_comment)

    # 添加边 - 简化的流程
    workflow.add_edge("fetch_pr_and_code_files", "intelligent_code_review")
    workflow.add_edge("intelligent_code_review", "post_review_comment")
    workflow.add_edge("post_review_comment", END)

    # 设置入口点
    workflow.set_entry_point("fetch_pr_and_code_files")

    # 编译图
    return workflow.compile()


# 运行代码审查
async def _review_single_file_async(
        file: FileInfo, pr_info: PRInfo
) -> Dict[str, Any]:
    """异步审查单个文件"""
    try:
        llm = get_llm()

        # 构建单文件审查提示
        prompt = _build_single_file_review_prompt(file, pr_info)

        # 异步调用LLM
        response = await llm.ainvoke(prompt)
        review_content = str(
            response.content if hasattr(response, "content") else response
        )

        # 解析单文件审查结果
        file_review = _parse_single_file_response(review_content, file)

        return file_review

    except Exception as e:
        logger.error(f"单文件审查失败 {file.filename}: {e}")
        return {
            "filename": file.filename,
            "score": 70,
            "issues": [{"type": "error", "title": "审查异常", "description": str(e)}],
            "positive_points": [],
            "summary": f"审查异常: {str(e)}",
        }


def _build_single_file_review_prompt(
        file: FileInfo, pr_info: PRInfo
) -> str:
    """构建单文件审查提示"""
    filename = file.filename
    status = file.status
    additions = file.additions
    deletions = file.deletions
    patch = _safe_get_string(file.patch)
    content = _safe_get_string(file.content)

    prompt = f"""
你是一个资深的代码审查专家。请对以下单个文件进行详细的代码审查。

## PR背景信息
- 标题: {_safe_get_string(pr_info.title)}
- 作者: {_safe_get_user_login(pr_info)}

## 文件信息
- 文件名: {filename}
- 状态: {status}
- 新增行数: {additions}
- 删除行数: {deletions}

## 变更内容 (diff):
```diff
{patch[:1500]}{'...' if len(patch) > 1500 else ''}
```

## 完整文件内容:
```
{content[:3000]}{'...' if len(content) > 3000 else ''}
```

## 审查要求
请从以下维度对这个文件进行深度审查：

1. **代码质量** (0-100分):
   - 可读性和可维护性
   - 代码复杂度
   - 命名规范
   - 代码结构

2. **安全性** (0-100分):
   - 潜在安全漏洞
   - 输入验证
   - 权限控制
   - 数据处理安全

3. **业务逻辑** (0-100分):
   - 逻辑正确性
   - 边界条件处理
   - 错误处理
   - 业务规则符合性

4. **性能** (0-100分):
   - 算法效率
   - 资源使用
   - 潜在性能瓶颈

5. **最佳实践** (0-100分):
   - 编码规范
   - 设计模式
   - 文档注释
   - 测试覆盖

## 输出格式
请严格按照以下JSON格式返回审查结果，确保JSON格式正确：

{{
    "filename": "{filename}",
    "overall_score": 85,
    "code_quality_score": 80,
    "security_score": 90,
    "business_score": 85,
    "performance_score": 80,
    "best_practices_score": 85,
    "issues": [
        {{
            "type": "warning",
            "title": "问题标题",
            "description": "详细描述",
            "line": 45,
            "severity": "warning",
            "category": "code_quality",
            "suggestion": "改进建议"
        }}
    ],
    "positive_points": [
        "优点1",
        "优点2"
    ],
    "summary": "对该文件的总体评价和建议"
}}


**重要提示**：
1. 必须返回有效的JSON格式
2. 所有字符串值必须用双引号包围
3. 数字值不要用引号
4. issues 中每个问题必须包含 severity 和 category 字段
5. severity 可选值: "info", "warning", "error", "critical"
6. category 可选值: "code_quality", "security", "performance", "best_practices", "documentation", "other"
"""
    return prompt


def _parse_single_file_response(response: str, file: Union[FileInfo, Dict[str, Any]]) -> Dict[str, Any]:
    """解析单文件审查响应"""
    import json
    import re

    # 处理FileInfo对象或字典格式
    if isinstance(file, FileInfo):
        filename = file.filename
    else:
        filename = file.get("filename", "unknown")

    try:
        # 尝试提取JSON - 改进的正则表达式
        json_patterns = [
            r"```json\s*(.*?)\s*```",  # 标准 json 代码块
            r"```\s*(.*?)\s*```",  # 普通代码块
            r"\{.*\}",  # 直接的 JSON 对象
        ]

        json_str = None
        for pattern in json_patterns:
            json_match = re.search(pattern, response, re.DOTALL)
            if json_match:
                json_str = (
                    json_match.group(1) if pattern != r"\{.*\}" else json_match.group(0)
                )
                break

        if not json_str:
            # 查找第一个{到最后一个}
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response[start:end]
            else:
                # 没有找到 JSON 格式，直接使用正则表达式提取
                logger.warning(f"未找到JSON格式，尝试使用正则表达式提取信息: {filename}")
                result = _extract_info_with_regex(response, filename)
                # 跳过 JSON 解析，直接进入验证阶段
                json_str = None

        # 如果找到了 JSON 字符串，尝试解析
        if json_str is not None:
            # 清理 JSON 字符串
            json_str = json_str.strip()

            # 尝试修复常见的 JSON 格式问题
            json_str = _fix_json_format(json_str)

            # 解析JSON
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                # 如果 JSON 解析失败，尝试使用正则表达式提取关键信息
                logger.warning(f"JSON解析失败，尝试使用正则表达式提取信息: {filename}")
                result = _extract_info_with_regex(response, filename)

        # 确保必要字段存在
        issues = result.get("issues", [])
        # 验证和修复 issues 格式
        validated_issues = []
        for issue in issues:
            if isinstance(issue, dict):
                # 确保必需字段存在
                validated_issue = {
                    "type": issue.get("type", "info"),
                    "title": issue.get("title", "未知问题"),
                    "description": issue.get("description", ""),
                    "line": issue.get("line", issue.get("line_start")),
                    "suggestion": issue.get("suggestion", ""),
                    "severity": issue.get(
                        "severity", issue.get("type", "info")
                    ),  # 确保有 severity
                    "category": issue.get("category", "other"),  # 确保有 category
                }
                validated_issues.append(validated_issue)

        file_review = {
            "filename": filename,
            "score": _safe_get_score(result.get("overall_score", result.get("score", 80))),
            "code_quality_score": _safe_get_score(result.get("code_quality_score", 80)),
            "security_score": _safe_get_score(result.get("security_score", 80)),
            "business_score": _safe_get_score(result.get("business_score", 80)),
            "performance_score": _safe_get_score(result.get("performance_score", 80)),
            "best_practices_score": _safe_get_score(
                result.get("best_practices_score", 80)
            ),
            "issues": validated_issues,
            "positive_points": result.get("positive_points", []),
            "summary": result.get("summary", f"文件 {filename} 审查完成"),
        }

        return file_review

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败 {filename}: {e}")
        logger.error(f"错误位置: 行{e.lineno}, 列{e.colno}, 字符{e.pos}")
        logger.debug(f"原始响应内容: {response[:1000]}...")  # 记录前1000字符用于调试
        if 'json_str' in locals():
            logger.debug(f"清理后的JSON: {json_str[:1000]}...")
    except Exception as e:
        logger.error(f"解析单文件响应失败 {filename}: {e}")
        logger.debug(f"原始响应内容: {response[:1000]}...")  # 记录前1000字符用于调试
        # 返回默认结果
        return {
            "filename": filename,
            "score": 75,
            "code_quality_score": 75,
            "security_score": 75,
            "business_score": 75,
            "performance_score": 75,
            "best_practices_score": 75,
            "issues": [
                {
                    "type": "warning",
                    "title": "解析失败",
                    "description": f"LLM 响应解析失败: {str(e)}",
                    "severity": "warning",
                    "category": "other",
                    "suggestion": "请检查 LLM 输出格式",
                }
            ],
            "positive_points": ["文件已审查"],
            "summary": f"文件 {filename} 审查完成（解析失败，使用默认结果）",
        }


def _fix_json_format(json_str: str) -> str:
    """修复常见的 JSON 格式问题"""
    import re

    # 移除可能的 markdown 标记
    json_str = re.sub(r'^```json\s*', '', json_str)
    json_str = re.sub(r'\s*```$', '', json_str)
    json_str = re.sub(r'^```\s*', '', json_str)

    # 修复常见的 JSON 格式问题
    # 1. 修复缺少逗号的问题 - 更精确的模式
    # 在字符串值后面缺少逗号
    json_str = re.sub(r'"\s*\n\s*"', '",\n    "', json_str)
    # 在数字值后面缺少逗号
    json_str = re.sub(r'(\d+)\s*\n\s*"', r'\1,\n    "', json_str)
    # 在布尔值后面缺少逗号
    json_str = re.sub(r'(true|false)\s*\n\s*"', r'\1,\n    "', json_str)
    # 在数组后面缺少逗号
    json_str = re.sub(r']\s*\n\s*"', '],\n    "', json_str)
    # 在对象后面缺少逗号
    json_str = re.sub(r'}\s*\n\s*"', '},\n    "', json_str)

    # 2. 修复多余的逗号
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    # 3. 修复不完整的 JSON（如果以逗号结尾，尝试补全）
    json_str = json_str.strip()
    if json_str.endswith(','):
        json_str = json_str[:-1]

    # 4. 如果 JSON 不完整，尝试补全
    if json_str.count('{') > json_str.count('}'):
        json_str += '}' * (json_str.count('{') - json_str.count('}'))
    if json_str.count('[') > json_str.count(']'):
        json_str += ']' * (json_str.count('[') - json_str.count(']'))

    return json_str


def _extract_info_with_regex(response: str, filename: str) -> Dict[str, Any]:
    """使用正则表达式从响应中提取关键信息，作为 JSON 解析失败的备用方案"""
    import re

    result = {
        "filename": filename,
        "overall_score": 75,
        "code_quality_score": 75,
        "security_score": 75,
        "business_score": 75,
        "performance_score": 75,
        "best_practices_score": 75,
        "issues": [],
        "positive_points": [],
        "summary": f"文件 {filename} 审查完成（使用正则表达式解析）"
    }

    try:
        # 提取评分
        score_patterns = [
            (r'"overall_score":\s*(\d+)', 'overall_score'),
            (r'"code_quality_score":\s*(\d+)', 'code_quality_score'),
            (r'"security_score":\s*(\d+)', 'security_score'),
            (r'"business_score":\s*(\d+)', 'business_score'),
            (r'"performance_score":\s*(\d+)', 'performance_score'),
            (r'"best_practices_score":\s*(\d+)', 'best_practices_score'),
        ]

        for pattern, key in score_patterns:
            match = re.search(pattern, response)
            if match:
                result[key] = int(match.group(1))

        # 提取总结
        summary_match = re.search(r'"summary":\s*"([^"]*)"', response)
        if summary_match:
            result["summary"] = summary_match.group(1)

        # 提取问题（简化版）
        issues = []
        issue_pattern = r'"title":\s*"([^"]*)".*?"description":\s*"([^"]*)"'
        issue_matches = re.findall(issue_pattern, response, re.DOTALL)

        for title, description in issue_matches:
            issues.append({
                "type": "info",
                "title": title,
                "description": description,
                "severity": "info",
                "category": "other",
                "suggestion": ""
            })

        result["issues"] = issues

        # 提取积极点
        positive_pattern = r'"positive_points":\s*\[(.*?)\]'
        positive_match = re.search(positive_pattern, response, re.DOTALL)
        if positive_match:
            positive_content = positive_match.group(1)
            positive_points = re.findall(r'"([^"]*)"', positive_content)
            result["positive_points"] = positive_points

    except Exception as e:
        logger.warning(f"正则表达式提取也失败: {e}")

    return result


def _safe_get_score(score: Any) -> int:
    """安全地获取评分"""
    try:
        if isinstance(score, (int, float)):
            return max(0, min(100, int(score)))
        elif isinstance(score, str):
            return max(0, min(100, int(float(score))))
        else:
            return 80
    except (ValueError, TypeError):
        return 80


def _calculate_overall_scores(file_reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算总体评分"""
    if not file_reviews:
        return {
            "overall_score": 100,
            "code_quality_score": 100,
            "security_score": 100,
            "business_score": 100,
            "summary": "没有文件需要审查",
            "standards_passed": 0,
            "standards_failed": 0,
            "standards_total": 0,
        }

    # 计算各维度平均分（使用安全的评分获取）
    total_files = len(file_reviews)

    avg_code_quality = (
            sum(_safe_get_score(fr.get("code_quality_score", 80)) for fr in file_reviews)
            / total_files
    )
    avg_security = (
            sum(_safe_get_score(fr.get("security_score", 80)) for fr in file_reviews)
            / total_files
    )
    avg_business = (
            sum(_safe_get_score(fr.get("business_score", 80)) for fr in file_reviews)
            / total_files
    )
    avg_performance = (
            sum(_safe_get_score(fr.get("performance_score", 80)) for fr in file_reviews)
            / total_files
    )
    avg_best_practices = (
            sum(_safe_get_score(fr.get("best_practices_score", 80)) for fr in file_reviews)
            / total_files
    )

    # 计算总体评分（加权平均）
    overall_score = (
            avg_code_quality * 0.25
            + avg_security * 0.25
            + avg_business * 0.25
            + avg_performance * 0.125
            + avg_best_practices * 0.125
    )

    # 统计问题数量（使用安全的评分获取）
    total_issues = sum(len(fr.get("issues", [])) for fr in file_reviews)
    high_score_files = sum(
        1 for fr in file_reviews if _safe_get_score(fr.get("score", 80)) >= 85
    )

    # 生成总结
    summary = f"审查了 {total_files} 个文件，发现 {total_issues} 个问题，{high_score_files} 个文件质量优秀"

    return {
        "overall_score": round(overall_score, 1),
        "code_quality_score": round(avg_code_quality, 1),
        "security_score": round(avg_security, 1),
        "business_score": round(avg_business, 1),
        "performance_score": round(avg_performance, 1),
        "best_practices_score": round(avg_best_practices, 1),
        "summary": summary,
        "standards_passed": max(0, total_files * 5 - total_issues),  # 估算
        "standards_failed": total_issues,
        "standards_total": total_files * 5,
    }


def _safe_get_user_login(pr_info: Union[PRInfo, Dict[str, Any]]) -> str:
    """安全地获取用户登录名"""
    try:
        if isinstance(pr_info, PRInfo):
            return pr_info.author.login
        elif isinstance(pr_info, dict):
            # 向后兼容旧的字典格式
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


def _safe_get_string(data: Any, default: str = "") -> str:
    """安全地获取字符串值"""
    if data is None:
        return default
    return str(data)


async def run_code_review_async(pr_info: Dict[str, Any]) -> Dict[str, Any]:
    """异步运行代码审查

    Args:
        pr_info: PR 信息，包含 repo 和 number

    Returns:
        审查结果
    """
    # 构造工作流
    graph = build_code_review_graph()

    # 解析作者信息
    author_data = pr_info.get("author", {})
    if isinstance(author_data, dict):
        author = UserInfo(**author_data)
    else:
        author = UserInfo(login="unknown")

    # 创建PR信息模型
    pr_info_model = PRInfo(
        repo=pr_info["repo"],
        number=pr_info["number"],
        platform=pr_info.get("platform", "github"),
        author=author,
        title=pr_info.get("title", ""),
        body=pr_info.get("body", ""),
        head_sha=pr_info.get("head_sha", ""),
        base_sha=pr_info.get("base_sha", ""),
        repo_full_name=pr_info.get("repo_full_name", pr_info["repo"])
    )

    # 初始状态
    initial_state = AgentState(
        pr_info=pr_info_model
    )

    # 异步执行图
    result = await graph.ainvoke(initial_state)

    # 转换结果为字典格式以保持向后兼容
    return _convert_state_to_dict(result)


def _convert_state_to_dict(state: Union[AgentState, Dict[str, Any]]) -> Dict[str, Any]:
    """将AgentState或字典状态转换为字典格式以保持向后兼容"""
    # 处理 LangGraph 返回的 AddableValuesDict 或其他字典类型
    if isinstance(state, dict):
        # 如果是字典类型，直接使用
        file_reviews_data = state.get("file_reviews", [])
        enhanced_analysis_data = state.get("enhanced_analysis")
        pr_info_data = state.get("pr_info", {})
        files_data = state.get("files", [])
        file_contents_data = state.get("file_contents", {})
        overall_summary_data = state.get("overall_summary")
        db_record_id_data = state.get("db_record_id")
    else:
        # 如果是 AgentState 对象
        file_reviews_data = state.file_reviews
        enhanced_analysis_data = state.enhanced_analysis
        pr_info_data = state.pr_info
        files_data = state.files
        file_contents_data = state.file_contents
        overall_summary_data = state.overall_summary
        db_record_id_data = state.db_record_id

    file_reviews = []
    for review in file_reviews_data:
        if isinstance(review, FileReviewInfo):
            file_reviews.append({
                "filename": review.filename,
                "score": review.score,
                "code_quality_score": review.code_quality_score,
                "security_score": review.security_score,
                "business_score": review.business_score,
                "performance_score": review.performance_score,
                "best_practices_score": review.best_practices_score,
                "issues": [issue.model_dump() for issue in review.issues],
                "positive_points": review.positive_points,
                "summary": review.summary,
            })
        else:
            file_reviews.append(review)

    # 处理增强分析数据
    enhanced_analysis = None
    if enhanced_analysis_data:
        if hasattr(enhanced_analysis_data, 'model_dump'):
            enhanced_analysis = enhanced_analysis_data.model_dump()
        else:
            enhanced_analysis = enhanced_analysis_data

    # 处理 PR 信息数据
    if hasattr(pr_info_data, 'model_dump'):
        pr_info_dict = pr_info_data.model_dump()
    else:
        pr_info_dict = pr_info_data

    # 处理文件数据
    files_list = []
    for f in files_data:
        if hasattr(f, 'model_dump'):
            files_list.append(f.model_dump())
        else:
            files_list.append(f)

    return {
        "pr_info": pr_info_dict,
        "files": files_list,
        "file_contents": file_contents_data,
        "file_reviews": file_reviews,
        "overall_summary": overall_summary_data,
        "enhanced_analysis": enhanced_analysis,
        "db_record_id": db_record_id_data,
    }


def run_code_review(pr_info: Dict[str, Any]) -> Dict[str, Any]:
    """运行代码审查 - 同步包装器

    Args:
        pr_info: PR 信息，包含 repo 和 number

    Returns:
        审查结果
    """
    import asyncio

    # 获取或创建事件循环
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果事件循环正在运行，创建新的事件循环
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, run_code_review_async(pr_info))
                return future.result()
        else:
            # 如果事件循环没有运行，直接使用
            return loop.run_until_complete(run_code_review_async(pr_info))
    except RuntimeError:
        # 如果没有事件循环，创建新的
        return asyncio.run(run_code_review_async(pr_info))
