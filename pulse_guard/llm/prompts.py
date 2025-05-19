"""
LLM 提示模板模块。
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 代码审查系统提示
CODE_REVIEW_SYSTEM_PROMPT = """你是一个专业的代码审查助手，负责分析代码质量并提供改进建议。

你的任务是:
1. 分析提供的代码文件
2. 识别代码中的问题和改进机会
3. 提供具体、可操作的建议
4. 关注代码质量、性能、安全性和最佳实践

请确保你的反馈:
- 具体且有建设性
- 提供明确的改进建议
- 解释为什么某些做法是问题或可以改进
- 如果代码已经很好，也要指出其优点

你的输出将用于生成 GitHub PR 评论，帮助开发者改进他们的代码。
"""

# PR 分析提示模板
PR_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CODE_REVIEW_SYSTEM_PROMPT),
    ("human", """
请分析以下 Pull Request 信息，并确定需要重点关注的方面:

PR 标题: {pr_title}
PR 描述: {pr_description}
修改的文件:
{files_summary}

请回答以下问题:
1. 这个 PR 的主要目的是什么?
2. 需要重点关注哪些文件和代码区域?
3. 应该关注哪些方面的代码质量问题?
4. 有没有特殊的上下文需要考虑?
    """),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# 文件审查提示模板
FILE_REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system", CODE_REVIEW_SYSTEM_PROMPT),
    ("human", """
请审查以下代码文件:

文件名: {filename}
文件类型: {file_type}
代码:
```
{file_content}
```

请提供详细的代码审查，包括:
1. 代码质量问题
2. 潜在的 bug 或错误
3. 性能优化机会
4. 安全隐患
5. 可读性和可维护性改进
6. 是否遵循最佳实践

对于每个问题，请提供:
- 问题描述
- 问题位置（行号）
- 严重程度（信息、警告、错误、严重）
- 改进建议

最后，请提供对该文件的总体评价。
    """),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# 总结提示模板
SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一个专业的代码审查助手，负责总结代码审查结果并提供整体评价。"""),
    ("human", """
请根据以下各文件的代码审查结果，生成一个总体评价:

{file_reviews}

请在总结中包括:
1. PR 的整体质量评价
2. 主要问题和模式
3. 关键改进建议
4. 积极的反馈和鼓励

你的总结将作为 PR 评论的开头部分，应该友好、专业且有建设性。
    """),
])
