"""
LangGraph 代码审查 Agent 实现。
"""
from typing import TypedDict, List, Dict, Any, Annotated, Sequence, Union, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

from pulse_guard.config import config
from pulse_guard.llm.client import get_llm
from pulse_guard.models.review import PRReview, FileReview, CodeIssue, SeverityLevel, IssueCategory
from pulse_guard.tools.github import get_pr_info, get_pr_files, get_file_content, post_pr_comment


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


# 节点函数
def analyze_pr(state: AgentState) -> AgentState:
    """分析 PR 信息并获取文件列表"""
    pr_info = state["pr_info"]

    # 获取 PR 详细信息
    pr_details = get_pr_info.invoke(input=f"{pr_info['repo']}|{pr_info['number']}")

    # 获取 PR 修改的文件列表
    files = get_pr_files.invoke(input=f"{pr_info['repo']}|{pr_info['number']}")

    # 限制文件数量
    max_files = config.review.max_files_per_review
    if len(files) > max_files:
        # 按照变更行数排序，优先审查变更较大的文件
        files.sort(key=lambda f: f["changes"], reverse=True)
        files = files[:max_files]

    # 更新状态
    return {
        **state,
        "pr_info": {**pr_info, **pr_details},
        "files": files,
        "file_contents": {},
        "current_file_index": 0,
        "file_reviews": [],
    }


def get_file_contents(state: AgentState) -> AgentState:
    """获取文件内容"""
    pr_info = state["pr_info"]
    files = state["files"]
    file_contents = state["file_contents"].copy()

    # 获取所有文件的内容
    for file in files:
        if file["filename"] not in file_contents and file["status"] != "removed":
            try:
                content = get_file_content.invoke(input=f"{pr_info['repo_full_name']}|{file['filename']}|{pr_info['head_sha']}")
                file_contents[file["filename"]] = content
            except Exception as e:
                # 如果获取文件内容失败，记录错误
                file_contents[file["filename"]] = f"Error fetching file content: {str(e)}"

    # 更新状态
    return {**state, "file_contents": file_contents}


def review_current_file(state: AgentState) -> AgentState:
    """审查当前文件"""
    files = state["files"]
    file_contents = state["file_contents"]
    current_file_index = state["current_file_index"]
    file_reviews = state["file_reviews"].copy()

    # 检查是否还有文件需要审查
    if current_file_index >= len(files):
        return {**state, "current_file_index": current_file_index}

    # 获取当前文件信息
    current_file = files[current_file_index]
    filename = current_file["filename"]

    # 如果文件已被删除，跳过审查
    if current_file["status"] == "removed":
        file_reviews.append({
            "filename": filename,
            "summary": "此文件已被删除，跳过审查。",
            "issues": []
        })
        return {
            **state,
            "current_file_index": current_file_index + 1,
            "file_reviews": file_reviews
        }

    # 获取文件内容
    content = file_contents.get(filename, "")
    if not content or content.startswith("Error fetching file content"):
        file_reviews.append({
            "filename": filename,
            "summary": f"无法获取文件内容: {content}",
            "issues": []
        })
        return {
            **state,
            "current_file_index": current_file_index + 1,
            "file_reviews": file_reviews
        }

    # 获取文件类型
    file_type = filename.split(".")[-1] if "." in filename else "unknown"

    # 使用 LLM 审查文件
    llm = get_llm()

    # 构建提示
    prompt = f"""
请审查以下代码文件:

文件名: {filename}
文件类型: {file_type}
代码:
```
{content}
```

请提供详细的代码审查，包括:
1. 代码质量问题
2. 潜在的 bug 或错误
3. 性能优化机会
4. 安全隐患
5. 可读性和可维护性改进
6. 是否遵循最佳实践

对于每个问题，请使用以下格式:
- 问题: [问题标题]
- 描述: [详细描述]
- 位置: [行号范围，如 10-15]
- 严重程度: [INFO|WARNING|ERROR|CRITICAL]
- 类别: [CODE_QUALITY|SECURITY|PERFORMANCE|BEST_PRACTICES|DOCUMENTATION|OTHER]
- 建议: [改进建议]

最后，请提供对该文件的总体评价。

请使用中文回复。
"""

    # 获取 LLM 响应
    response = llm.invoke(prompt)
    review_text = response.content

    # 解析审查结果
    issues = []
    summary = ""

    # 简单解析，实际项目中可能需要更复杂的解析逻辑
    lines = review_text.split("\n")
    current_issue = {}

    for line in lines:
        line = line.strip()

        # 检查是否是总体评价部分
        if "总体评价" in line or "总结" in line:
            # 收集后续行作为总结
            summary_start_index = lines.index(line) + 1
            summary = "\n".join(lines[summary_start_index:]).strip()
            break

        # 解析问题
        if line.startswith("- 问题:") or line.startswith("问题:"):
            # 保存之前的问题
            if current_issue and "title" in current_issue:
                try:
                    issues.append(CodeIssue(
                        title=current_issue.get("title", ""),
                        description=current_issue.get("description", ""),
                        severity=current_issue.get("severity", SeverityLevel.INFO),
                        category=current_issue.get("category", IssueCategory.OTHER),
                        line_start=current_issue.get("line_start"),
                        line_end=current_issue.get("line_end"),
                        suggestion=current_issue.get("suggestion", "")
                    ))
                except Exception:
                    # 如果解析失败，忽略该问题
                    pass

            # 开始新问题
            current_issue = {"title": line.split(":", 1)[1].strip()}
        elif line.startswith("- 描述:") or line.startswith("描述:"):
            current_issue["description"] = line.split(":", 1)[1].strip()
        elif line.startswith("- 位置:") or line.startswith("位置:"):
            location = line.split(":", 1)[1].strip()
            try:
                if "-" in location:
                    start, end = location.split("-")
                    current_issue["line_start"] = int(start.strip())
                    current_issue["line_end"] = int(end.strip())
                else:
                    line_num = int(location.strip())
                    current_issue["line_start"] = line_num
                    current_issue["line_end"] = line_num
            except ValueError:
                # 如果解析失败，不设置行号
                pass
        elif line.startswith("- 严重程度:") or line.startswith("严重程度:"):
            severity_text = line.split(":", 1)[1].strip().upper()
            try:
                current_issue["severity"] = SeverityLevel(severity_text.lower())
            except ValueError:
                # 如果无效的严重程度，使用默认值
                if "critical" in severity_text.lower():
                    current_issue["severity"] = SeverityLevel.CRITICAL
                elif "error" in severity_text.lower():
                    current_issue["severity"] = SeverityLevel.ERROR
                elif "warning" in severity_text.lower():
                    current_issue["severity"] = SeverityLevel.WARNING
                else:
                    current_issue["severity"] = SeverityLevel.INFO
        elif line.startswith("- 类别:") or line.startswith("类别:"):
            category_text = line.split(":", 1)[1].strip().upper()
            try:
                current_issue["category"] = IssueCategory(category_text.lower())
            except ValueError:
                # 如果无效的类别，使用默认值
                if "security" in category_text.lower():
                    current_issue["category"] = IssueCategory.SECURITY
                elif "performance" in category_text.lower():
                    current_issue["category"] = IssueCategory.PERFORMANCE
                elif "best" in category_text.lower():
                    current_issue["category"] = IssueCategory.BEST_PRACTICES
                elif "doc" in category_text.lower():
                    current_issue["category"] = IssueCategory.DOCUMENTATION
                else:
                    current_issue["category"] = IssueCategory.CODE_QUALITY
        elif line.startswith("- 建议:") or line.startswith("建议:"):
            current_issue["suggestion"] = line.split(":", 1)[1].strip()

    # 保存最后一个问题
    if current_issue and "title" in current_issue:
        try:
            issues.append(CodeIssue(
                title=current_issue.get("title", ""),
                description=current_issue.get("description", ""),
                severity=current_issue.get("severity", SeverityLevel.INFO),
                category=current_issue.get("category", IssueCategory.OTHER),
                line_start=current_issue.get("line_start"),
                line_end=current_issue.get("line_end"),
                suggestion=current_issue.get("suggestion", "")
            ))
        except Exception:
            # 如果解析失败，忽略该问题
            pass

    # 如果没有提取到总结，使用默认总结
    if not summary:
        summary = f"对文件 {filename} 进行了代码审查，" + (
            f"发现了 {len(issues)} 个问题。" if issues else "没有发现明显问题。"
        )

    # 添加文件审查结果
    file_reviews.append({
        "filename": filename,
        "summary": summary,
        "issues": [issue.dict() for issue in issues]
    })

    # 更新状态
    return {
        **state,
        "current_file_index": current_file_index + 1,
        "file_reviews": file_reviews
    }


def check_more_files(state: AgentState) -> Union[str, Dict[str, Any]]:
    """检查是否还有更多文件需要审查"""
    current_file_index = state["current_file_index"]
    files = state["files"]

    if current_file_index < len(files):
        return "review_more_files"
    else:
        return "generate_summary"


def generate_summary(state: AgentState) -> AgentState:
    """生成总体评价"""
    file_reviews = state["file_reviews"]

    # 如果没有文件审查结果，返回默认总结
    if not file_reviews:
        return {
            **state,
            "overall_summary": "没有找到需要审查的文件。"
        }

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
1. PR 的整体质量评价
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
    """发布审查评论"""
    pr_info = state["pr_info"]
    file_reviews = state["file_reviews"]
    overall_summary = state["overall_summary"]

    # 创建 PR 审查结果
    pr_review = PRReview(
        pr_number=pr_info["number"],
        repo_full_name=pr_info["repo_full_name"],
        overall_summary=overall_summary,
        file_reviews=[
            FileReview(
                filename=review["filename"],
                summary=review["summary"],
                issues=[CodeIssue(**issue) for issue in review["issues"]]
            )
            for review in file_reviews
        ]
    )

    # 格式化评论
    comment = pr_review.format_comment()

    # 发布评论
    post_pr_comment.invoke(input=f"{pr_info['repo_full_name']}|{pr_info['number']}|{comment}")

    # 更新状态
    return {**state, "comment": comment}


# 构建 LangGraph
def build_code_review_graph():
    """构建代码审查 LangGraph"""
    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("analyze_pr", analyze_pr)
    workflow.add_node("get_file_contents", get_file_contents)
    workflow.add_node("review_current_file", review_current_file)
    workflow.add_node("generate_summary", generate_summary)
    workflow.add_node("post_review_comment", post_review_comment)

    # 添加边
    workflow.add_edge("analyze_pr", "get_file_contents")
    workflow.add_edge("get_file_contents", "review_current_file")
    workflow.add_conditional_edges(
        "review_current_file",
        check_more_files,
        {
            "review_more_files": "review_current_file",
            "generate_summary": "generate_summary"
        }
    )
    workflow.add_edge("generate_summary", "post_review_comment")
    workflow.add_edge("post_review_comment", END)

    # 设置入口点
    workflow.set_entry_point("analyze_pr")

    # 编译图
    return workflow.compile()


# 运行代码审查
def run_code_review(pr_info: Dict[str, Any]) -> Dict[str, Any]:
    """运行代码审查

    Args:
        pr_info: PR 信息，包含 repo 和 number

    Returns:
        审查结果
    """
    graph = build_code_review_graph()

    # 初始状态
    initial_state = {
        "messages": [],
        "pr_info": pr_info,
        "files": [],
        "file_contents": {},
        "current_file_index": 0,
        "file_reviews": [],
        "overall_summary": None
    }

    # 执行图
    result = graph.invoke(initial_state)
    return result
