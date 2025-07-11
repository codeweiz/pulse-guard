"""
LangGraph 代码审查 Agent 实现。
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from pulse_guard.agent.data_validator import data_validator
from pulse_guard.llm.client import get_llm
from pulse_guard.models.review import (
    CodeIssue,
    FileReview,
    IssueCategory,
    PRReview,
    SeverityLevel,
)
from pulse_guard.platforms import get_platform_provider

# 配置日志
logger = logging.getLogger(__name__)


# 定义 Agent 状态类型
class AgentState(TypedDict):
    """Agent 状态"""

    messages: List[Union[AIMessage, HumanMessage]]
    pr_info: Dict[str, Any]
    files: List[Dict[str, Any]]
    file_contents: Dict[str, str]
    current_file_index: int
    file_reviews: List[Dict[str, Any]]
    overall_summary: Optional[str]
    enhanced_analysis: Optional[Dict[str, Any]]
    db_record_id: Optional[int]


# 代码文件扩展名
CODE_EXTENSIONS = {
    ".py",
    ".vue",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".scala",
    ".cs",
    ".vb",
    ".sql",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".css",
    ".scss",
    ".less",
    ".sh",
    ".bash",
    ".ps1",
    ".bat",
    ".dockerfile",
    ".makefile",
    ".md",
    ".txt",
    ".cfg",
    ".conf",
    ".ini",
    ".toml",
    ".properties",
    ".gradle",
    ".maven",
    ".sbt",
    ".cmake",
    ".r",
    ".m",
    ".pl",
    ".lua",
}

# 跳过的文件模式
SKIP_PATTERNS = [
    r".*\.(png|jpg|jpeg|gif|svg|ico|bmp|tiff|webp)$",  # 图片
    r".*\.(pdf|doc|docx|xls|xlsx|ppt|pptx)$",  # 文档
    r".*\.(zip|tar|gz|rar|7z|bz2)$",  # 压缩包
    r".*\.(mp4|avi|mov|wmv|flv|mp3|wav|ogg)$",  # 媒体文件
    r"(^|.*/)node_modules/.*",  # 依赖目录
    r"(^|.*/)\.git/.*",  # Git目录
    r".*\.min\.(js|css)$",  # 压缩文件
    r".*\.(lock|log)$",  # 锁文件和日志
]


def _is_code_file(filename: str) -> bool:
    """判断是否为代码文件"""
    import re

    # 检查是否匹配跳过模式（使用 search 而不是 match 来匹配路径中的任何位置）
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, filename, re.IGNORECASE):
            return False

    # 特殊文件名检查（优先级最高）
    code_filenames = {
        "makefile",
        "dockerfile",
        "rakefile",
        "gemfile",
        "podfile",
        "requirements.txt",
        "package-lock.json",
        "yarn.lock",
        "composer.lock",
        ".gitignore",
        ".gitattributes",
        ".dockerignore",
        ".eslintrc",
        ".prettierrc",
        ".babelrc",
        ".editorconfig",
        ".env",
        ".env.example",
        ".env.local",
        "license",
        "changelog",
        "contributing",
        "authors",
        "maintainers",
    }

    # 检查完整文件名
    if filename.lower() in code_filenames:
        return True

    # 检查文件名（不含路径）
    basename = filename.split("/")[-1].lower()
    if basename in code_filenames:
        return True

    # 检查文件扩展名
    if "." in filename and not filename.startswith("."):
        ext = "." + filename.split(".")[-1].lower()
        return ext in CODE_EXTENSIONS

    return False


def fetch_pr_and_code_files(state: AgentState) -> AgentState:
    """获取PR信息和代码文件内容（合并原来的analyze_pr和get_file_contents）"""
    pr_info = state["pr_info"]

    # 验证和清理PR信息
    validated_pr_info = data_validator.validate_pr_info(pr_info)
    platform = validated_pr_info.get("platform", "github")

    # 获取平台提供者
    provider = get_platform_provider(platform)

    # 获取 PR 详细信息
    pr_details = provider.get_pr_info(
        validated_pr_info["repo"], validated_pr_info["number"]
    )

    # 验证和合并PR详细信息
    merged_pr_info = data_validator.validate_pr_info(
        {**validated_pr_info, **pr_details}
    )

    # 获取 PR 修改的文件列表
    all_files = provider.get_pr_files(
        validated_pr_info["repo"], validated_pr_info["number"]
    )

    # 验证和清理文件信息
    validated_files = data_validator.validate_files_info(all_files)

    # 过滤出代码文件
    code_files = [f for f in validated_files if _is_code_file(f["filename"])]

    logger.info(
        f"总文件数: {len(all_files)}, 验证后文件数: {len(validated_files)}, 代码文件数: {len(code_files)}"
    )

    # 获取所有代码文件的内容
    file_contents = {}
    for file in code_files:
        if file["status"] != "removed":
            try:
                content = provider.get_file_content(
                    merged_pr_info["repo_full_name"],
                    file["filename"],
                    merged_pr_info["head_sha"],
                )
                file_contents[file["filename"]] = content
            except Exception as e:
                # 如果获取文件内容失败，记录错误
                file_contents[file["filename"]] = (
                    f"Error fetching file content: {str(e)}"
                )
                logger.warning(f"获取文件内容失败 {file['filename']}: {e}")

    # 将文件内容合并到文件信息中
    enhanced_files = []
    for file in code_files:
        enhanced_file = {**file, "content": file_contents.get(file["filename"], "")}
        enhanced_files.append(enhanced_file)

    # 更新状态
    return {
        **state,
        "pr_info": merged_pr_info,
        "files": enhanced_files,
        "file_contents": file_contents,
        "current_file_index": 0,
        "file_reviews": [],
    }


async def intelligent_code_review(state: AgentState) -> AgentState:
    """智能代码审查 - 按文件并发调用LLM"""
    pr_info = state["pr_info"]
    files = state["files"]

    if not files:
        logger.warning("没有代码文件需要审查")
        return {
            **state,
            "file_reviews": [],
            "overall_summary": "没有代码文件需要审查",
            "enhanced_analysis": {
                "overall_score": 100,
                "code_quality_score": 100,
                "security_score": 100,
                "business_score": 100,
                "file_results": [],
                "summary": "没有代码文件需要审查",
            },
        }

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
                logger.error(f"文件 {file['filename']} 审查异常: {result}")
                # 添加失败的默认结果
                file_reviews.append(
                    {
                        "filename": file["filename"],
                        "score": 70,
                        "issues": [
                            {
                                "type": "error",
                                "title": "审查失败",
                                "description": str(result),
                            }
                        ],
                        "positive_points": [],
                        "summary": f"审查失败: {str(result)}",
                    }
                )
            else:
                file_reviews.append(result)
                logger.info(f"文件 {file['filename']} 审查完成")

        # 计算总体评分
        overall_result = _calculate_overall_scores(file_reviews)

        logger.info(f"并发审查完成，总体评分: {overall_result['overall_score']}")

        return {
            **state,
            "file_reviews": file_reviews,
            "overall_summary": overall_result.get("summary", "并发审查完成"),
            "enhanced_analysis": {
                "overall_score": overall_result.get("overall_score", 80),
                "code_quality_score": overall_result.get("code_quality_score", 80),
                "security_score": overall_result.get("security_score", 80),
                "business_score": overall_result.get("business_score", 80),
                "file_results": file_reviews,
                "summary": overall_result.get("summary", "并发审查完成"),
                "standards_passed": overall_result.get("standards_passed", 0),
                "standards_failed": overall_result.get("standards_failed", 0),
                "standards_total": overall_result.get("standards_total", 0),
            },
        }

    except Exception as e:
        logger.error(f"并发审查失败: {e}")
        # 降级到简单审查
        return _fallback_simple_review(state)


def generate_summary(state: AgentState) -> AgentState:
    """生成总体评价"""
    file_reviews = state["file_reviews"]
    enhanced_analysis = state.get("enhanced_analysis")

    # 如果有增强分析结果，优先使用
    if enhanced_analysis:
        return {**state, "overall_summary": enhanced_analysis["summary"]}

    # 如果没有文件审查结果，返回默认总结
    if not file_reviews:
        return {**state, "overall_summary": "没有找到需要审查的文件。"}

    # 构建文件审查摘要
    file_reviews_text = ""
    for review in file_reviews:
        filename = review["filename"]
        summary = review["summary"]
        issues_count = len(review["issues"])

        file_reviews_text += f"## {filename}\n"
        file_reviews_text += f"- 摘要: {summary}\n"
        file_reviews_text += f"- 问题数: {issues_count}\n"

        if issues_count > 0:
            file_reviews_text += "- 问题列表:\n"
            for issue in review["issues"]:
                file_reviews_text += f"  - [{issue['severity']}] {issue['title']}\n"

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
    overall_summary = response.content

    # 更新状态
    return {**state, "overall_summary": overall_summary}


def post_review_comment(state: AgentState) -> AgentState:
    """发布审查评论并保存到数据库"""
    pr_info = state["pr_info"]
    platform = pr_info.get("platform", "github")
    file_reviews = state["file_reviews"]
    overall_summary = state["overall_summary"]
    enhanced_analysis = state.get("enhanced_analysis")

    # 首先保存审查结果到数据库
    try:
        from pulse_guard.database import DatabaseManager

        db_record_id = DatabaseManager.save_complete_review_result(
            repo_full_name=pr_info.get("repo_full_name", pr_info.get("repo", "")),
            pr_number=pr_info.get("number", 0),
            pr_title=pr_info.get("title", ""),
            pr_description=pr_info.get("description", ""),
            pr_author=pr_info.get("author", ""),
            platform=platform,
            review_result={
                "enhanced_analysis": enhanced_analysis,
                "file_reviews": file_reviews,
            },
        )
        logger.info(f"审查结果已保存到数据库，记录ID: {db_record_id}")

        # 更新状态中的数据库记录ID
        state = {**state, "db_record_id": db_record_id}

    except Exception as e:
        logger.error(f"保存审查结果到数据库失败: {e}")
        # 继续执行，不因为数据库保存失败而中断评论发布

    # 创建增强的评论内容
    comment_parts = []

    # 添加增强分析结果
    if enhanced_analysis:
        comment_parts.append("# 🔍 代码审查报告")
        comment_parts.append("")
        comment_parts.append("## 📊 评分概览")
        comment_parts.append(
            f"- **总体评分**: {enhanced_analysis['overall_score']:.1f}/100"
        )
        comment_parts.append(
            f"- **业务逻辑**: {enhanced_analysis['business_score']:.1f}/100"
        )
        comment_parts.append(
            f"- **代码质量**: {enhanced_analysis['code_quality_score']:.1f}/100"
        )
        comment_parts.append(
            f"- **安全性**: {enhanced_analysis['security_score']:.1f}/100"
        )
        comment_parts.append(
            f"- **规范通过率**: {enhanced_analysis['standards_passed']}/{enhanced_analysis['standards_total']}"
        )
        comment_parts.append("")
        comment_parts.append("## 📝 总体评价")
        comment_parts.append(enhanced_analysis["summary"])
        comment_parts.append("")

        # 添加文件影响分析
        if enhanced_analysis.get("file_results"):
            comment_parts.append("## 📁 文件影响分析")
            for fa in enhanced_analysis["file_results"]:
                # 安全地获取影响级别，如果没有则使用默认值
                impact_level = fa.get("impact_level", fa.get("type", "medium"))
                impact_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴",
                }.get(impact_level, "⚪")

                comment_parts.append(f"### {impact_emoji} `{fa['filename']}`")
                comment_parts.append(f"- **影响级别**: {impact_level}")
                comment_parts.append(
                    f"- **代码质量**: {fa.get('code_quality_score', 80):.1f}/100"
                )
                comment_parts.append(
                    f"- **安全评分**: {fa.get('security_score', 80):.1f}/100"
                )
                comment_parts.append(f"- **问题数量**: {len(fa.get('issues', []))}")
                comment_parts.append(
                    f"- **业务影响**: {fa.get('summary', fa.get('business_impact', '无特殊影响'))}"
                )
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
        pr_number=pr_info["number"],
        repo_full_name=pr_info["repo_full_name"],
        overall_summary=overall_summary,
        file_reviews=[
            FileReview(
                filename=review["filename"],
                summary=review["summary"],
                issues=[
                    _safe_create_code_issue(issue) for issue in review.get("issues", [])
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
            pr_info["repo_full_name"],
            pr_info["number"],
            comment_text,
            max_length=max_length,
        )

        # 统计发布结果
        success_count = sum(1 for r in results if "error" not in r)
        total_count = len(results)

        if success_count == total_count:
            print(f"✅ 已发布审查评论到 PR #{pr_info['number']} (共 {total_count} 条)")
        else:
            print(
                f"⚠️ 部分评论发布成功: {success_count}/{total_count} 条到 PR #{pr_info['number']}"
            )

    except Exception as e:
        print(f"❌ 发布评论失败: {str(e)}")
        # 如果分批发布失败，尝试发布简化版本
        try:
            simplified_comment = _create_fallback_comment(
                file_reviews, enhanced_analysis
            )
            provider.post_pr_comment(
                pr_info["repo_full_name"], pr_info["number"], simplified_comment
            )
            print(f"✅ 已发布简化评论到 PR #{pr_info['number']}")
        except Exception as fallback_error:
            print(f"❌ 简化评论也发布失败: {str(fallback_error)}")

    # 更新状态
    return {**state, "comment": comment_text}


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
    file_reviews: List[Dict[str, Any]], enhanced_analysis: Dict[str, Any] = None
) -> str:
    """创建极简的备用评论，确保能够发布"""
    parts = []

    # 基本统计
    total_files = len(file_reviews)
    total_issues = sum(len(review.get("issues", [])) for review in file_reviews)
    critical_issues = sum(
        1
        for review in file_reviews
        for issue in review.get("issues", [])
        if issue.get("severity") == "critical"
    )

    parts.append("# 🔍 代码审查完成")
    parts.append("")
    parts.append(f"📊 **统计**: {total_files} 个文件，{total_issues} 个问题")

    if critical_issues > 0:
        parts.append(f"🚨 **严重问题**: {critical_issues} 个，请优先处理")

    if enhanced_analysis:
        score = enhanced_analysis.get("overall_score", 80)
        parts.append(f"📈 **总体评分**: {score:.1f}/100")

    parts.append("")
    parts.append("💡 详细报告请查看完整分析或联系管理员")

    return "\n".join(parts)


# 构建 LangGraph
def build_code_review_graph():
    """构建简化的代码审查 LangGraph"""
    # 创建图
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
    file: Dict[str, Any], pr_info: Dict[str, Any]
) -> Dict[str, Any]:
    """异步审查单个文件"""
    try:
        llm = get_llm()

        # 构建单文件审查提示
        prompt = _build_single_file_review_prompt(file, pr_info)

        # 异步调用LLM
        response = await llm.ainvoke(prompt)
        review_content = (
            response.content if hasattr(response, "content") else str(response)
        )

        # 解析单文件审查结果
        file_review = _parse_single_file_response(review_content, file)

        return file_review

    except Exception as e:
        logger.error(f"单文件审查失败 {file.get('filename', 'unknown')}: {e}")
        return {
            "filename": file.get("filename", "unknown"),
            "score": 70,
            "issues": [{"type": "error", "title": "审查异常", "description": str(e)}],
            "positive_points": [],
            "summary": f"审查异常: {str(e)}",
        }


def _review_single_file(
    file: Dict[str, Any], pr_info: Dict[str, Any]
) -> Dict[str, Any]:
    """审查单个文件 - 保留同步版本用于向后兼容"""
    try:
        llm = get_llm()

        # 构建单文件审查提示
        prompt = _build_single_file_review_prompt(file, pr_info)

        # 调用LLM
        response = llm.invoke(prompt)
        review_content = (
            response.content if hasattr(response, "content") else str(response)
        )

        # 解析单文件审查结果
        file_review = _parse_single_file_response(review_content, file)

        return file_review

    except Exception as e:
        logger.error(f"单文件审查失败 {file.get('filename', 'unknown')}: {e}")
        return {
            "filename": file.get("filename", "unknown"),
            "score": 70,
            "issues": [{"type": "error", "title": "审查异常", "description": str(e)}],
            "positive_points": [],
            "summary": f"审查异常: {str(e)}",
        }


def _build_single_file_review_prompt(
    file: Dict[str, Any], pr_info: Dict[str, Any]
) -> str:
    """构建单文件审查提示"""
    filename = file.get("filename", "unknown")
    status = file.get("status", "modified")
    additions = file.get("additions", 0)
    deletions = file.get("deletions", 0)
    patch = _safe_get_string(file.get("patch", ""))
    content = _safe_get_string(file.get("content", ""))

    prompt = f"""
你是一个资深的代码审查专家。请对以下单个文件进行详细的代码审查。

## PR背景信息
- 标题: {_safe_get_string(pr_info.get('title', ''))}
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

```json
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
```

**重要提示**：
1. 必须返回有效的JSON格式
2. 所有字符串值必须用双引号包围
3. 数字值不要用引号
4. issues 中每个问题必须包含 severity 和 category 字段
5. severity 可选值: "info", "warning", "error", "critical"
6. category 可选值: "code_quality", "security", "performance", "best_practices", "documentation", "other"
"""
    return prompt


def _parse_single_file_response(response: str, file: Dict[str, Any]) -> Dict[str, Any]:
    """解析单文件审查响应"""
    import json
    import re

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
                raise ValueError("未找到JSON格式")

        # 清理 JSON 字符串
        json_str = json_str.strip()

        # 解析JSON
        result = json.loads(json_str)

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
            "score": _safe_get_score(result.get("overall_score", 80)),
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

    except Exception as e:
        logger.error(f"解析单文件响应失败 {filename}: {e}")
        logger.debug(f"原始响应内容: {response[:500]}...")  # 记录前500字符用于调试
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


def _safe_get_user_login(pr_info: Dict[str, Any]) -> str:
    """安全地获取用户登录名"""
    try:
        user = pr_info.get("user", "")
        if isinstance(user, dict):
            return user.get("login", "unknown")
        elif isinstance(user, str):
            return user
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


def _build_comprehensive_review_prompt(
    pr_info: Dict[str, Any], files: List[Dict[str, Any]]
) -> str:
    """构建综合审查提示"""

    # 构建文件信息
    files_info = []
    for file in files:
        file_info = f"""
## 文件: {file.get('filename', 'unknown')}
- 状态: {file.get('status', 'unknown')}
- 新增行数: {file.get('additions', 0)}
- 删除行数: {file.get('deletions', 0)}

### 变更内容 (diff):
```diff
{_safe_get_string(file.get('patch', '无diff信息'))[:1000]}...
```

### 完整文件内容:
```
{_safe_get_string(file.get('content', '无法获取文件内容'))[:2000]}...
```
"""
        files_info.append(file_info)

    files_text = "\n".join(files_info)

    prompt = f"""
你是一个资深的代码审查专家。请对以下PR进行全面的代码审查。

## PR信息
- 标题: {_safe_get_string(pr_info.get('title', ''))}
- 描述: {_safe_get_string(pr_info.get('body', ''))[:500]}...
- 作者: {_safe_get_user_login(pr_info)}

## 代码文件分析
{files_text}

## 审查要求
请从以下维度对每个文件进行审查：
1. **代码质量**: 可读性、可维护性、复杂度
2. **安全性**: 潜在安全漏洞、输入验证
3. **业务逻辑**: 逻辑正确性、边界条件处理
4. **性能**: 算法效率、资源使用
5. **最佳实践**: 编码规范、设计模式

## 输出格式
请以JSON格式返回审查结果：
```json
{{
    "overall_score": 85,
    "code_quality_score": 80,
    "security_score": 90,
    "business_score": 85,
    "file_reviews": [
        {{
            "filename": "src/main.py",
            "score": 85,
            "issues": [
                {{
                    "type": "warning",
                    "title": "函数复杂度过高",
                    "description": "process_data函数包含过多逻辑分支",
                    "line": 45,
                    "suggestion": "建议拆分为多个小函数"
                }}
            ],
            "positive_points": ["良好的错误处理", "清晰的变量命名"]
        }}
    ],
    "summary": "整体代码质量良好，建议优化函数复杂度"
}}
```

请确保返回有效的JSON格式。
"""
    return prompt


# 旧的解析函数已移动到 output_parser.py 中


def _fallback_simple_review(state: AgentState) -> AgentState:
    """降级到简单审查"""
    files = state["files"]

    file_reviews = []
    for file in files:
        file_reviews.append(
            {
                "filename": file["filename"],
                "score": 80,
                "issues": [],
                "positive_points": ["简单审查完成"],
            }
        )

    return {
        **state,
        "file_reviews": file_reviews,
        "overall_summary": "使用简单审查模式完成",
        "enhanced_analysis": {
            "overall_score": 80,
            "code_quality_score": 80,
            "security_score": 80,
            "business_score": 80,
            "file_results": file_reviews,
            "summary": "使用简单审查模式完成",
            "standards_passed": len(files) * 3,  # 估算
            "standards_failed": len(files) * 2,  # 估算
            "standards_total": len(files) * 5,
        },
    }


async def run_code_review_async(pr_info: Dict[str, Any]) -> Dict[str, Any]:
    """异步运行代码审查

    Args:
        pr_info: PR 信息，包含 repo 和 number

    Returns:
        审查结果
    """
    # 构造工作流
    graph = build_code_review_graph()

    # 初始状态
    initial_state = {
        "messages": [],
        "pr_info": pr_info,
        "files": [],
        "file_contents": {},
        "current_file_index": 0,
        "file_reviews": [],
        "overall_summary": None,
        "enhanced_analysis": None,
        "db_record_id": None,
    }

    # 异步执行图
    result = await graph.ainvoke(initial_state)
    return result


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
