"""代码审查提示模板"""


class ReviewPrompts:
    """代码审查提示模板"""

    SINGLE_FILE_REVIEW_TEMPLATE = """
你是一个资深的代码审查专家。请对以下单个文件进行详细的代码审查。

## PR背景信息
- 标题: {pr_title}
- 作者: {pr_author}

## 文件信息
- 文件名: {filename}
- 状态: {status}
- 新增行数: {additions}
- 删除行数: {deletions}

## 变更内容 (diff):
```diff
{patch}
```

## 完整文件内容:
```
{content}
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

    OVERALL_SUMMARY_TEMPLATE = """
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


# 全局提示模板实例
review_prompts = ReviewPrompts()
