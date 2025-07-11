"""
测试 Vue 文件解析，模拟原始错误场景
验证对 packages/base/src/views/login/index.vue 类似文件的处理
"""

import pytest
from pulse_guard.agent.graph import _parse_single_file_response
from pulse_guard.models.workflow import FileInfo


def test_vue_file_json_parsing_error():
    """测试 Vue 文件的 JSON 解析错误修复"""
    
    # 模拟原始错误中的响应 - 在第26行第37列缺少逗号
    vue_response_with_error = '''
    ```json
    {
        "filename": "packages/base/src/views/login/index.vue",
        "overall_score": 85,
        "code_quality_score": 80,
        "security_score": 90,
        "business_score": 85,
        "performance_score": 80,
        "best_practices_score": 85,
        "issues": [
            {
                "type": "warning",
                "title": "Vue component structure",
                "description": "Consider using composition API"
                "severity": "warning",
                "category": "best_practices",
                "line": 15,
                "suggestion": "Use composition API for better type safety"
            },
            {
                "type": "info",
                "title": "Template optimization",
                "description": "Template could be optimized",
                "severity": "info",
                "category": "performance"
            }
        ],
        "positive_points": [
            "Good component structure",
            "Clear naming conventions"
        ],
        "summary": "Vue component with good structure but could use modern patterns"
    }
    ```
    '''
    
    test_file = FileInfo(filename="packages/base/src/views/login/index.vue")
    
    # 应该能够处理这种 JSON 错误
    result = _parse_single_file_response(vue_response_with_error, test_file)
    
    # 验证结果
    assert result["filename"] == "packages/base/src/views/login/index.vue"
    assert isinstance(result["score"], int)
    assert result["score"] > 0
    assert isinstance(result["issues"], list)
    assert len(result["issues"]) >= 1  # 至少应该有一个问题
    assert isinstance(result["positive_points"], list)
    assert isinstance(result["summary"], str)
    
    # 验证问题结构
    for issue in result["issues"]:
        assert "type" in issue
        assert "title" in issue
        assert "description" in issue
        assert "severity" in issue
        assert "category" in issue


def test_vue_file_with_multiple_json_errors():
    """测试包含多个 JSON 错误的 Vue 文件响应"""
    
    # 模拟包含多个 JSON 格式错误的响应
    broken_vue_response = '''
    {
        "filename": "src/components/LoginForm.vue"
        "overall_score": 75
        "code_quality_score": 70,
        "security_score": 85
        "business_score": 75,
        "performance_score": 80,
        "best_practices_score": 70,
        "issues": [
            {
                "type": "error"
                "title": "Missing validation",
                "description": "Form lacks proper validation"
                "severity": "error",
                "category": "security",
                "line": 42
            }
        ]
        "positive_points": ["Responsive design"],
        "summary": "Component needs security improvements"
    '''
    
    test_file = FileInfo(filename="src/components/LoginForm.vue")
    
    # 应该能够处理多个 JSON 错误
    result = _parse_single_file_response(broken_vue_response, test_file)
    
    assert result["filename"] == "src/components/LoginForm.vue"
    assert isinstance(result["score"], int)
    assert isinstance(result["issues"], list)


def test_vue_file_completely_malformed():
    """测试完全格式错误的 Vue 文件响应"""
    
    # 模拟完全无法解析的响应
    malformed_response = '''
    This is a review of the Vue file packages/base/src/views/login/index.vue
    
    The file has some issues:
    - Missing proper validation
    - Could use better error handling
    
    Overall score would be around 75/100
    
    Some positive aspects:
    - Good component structure
    - Clean template
    '''
    
    test_file = FileInfo(filename="packages/base/src/views/login/index.vue")
    
    # 应该返回默认结果或正则表达式提取的结果
    result = _parse_single_file_response(malformed_response, test_file)

    assert result["filename"] == "packages/base/src/views/login/index.vue"
    assert isinstance(result["score"], int)
    assert isinstance(result["issues"], list)  # 可能为空，但应该是列表


def test_vue_file_with_regex_extraction():
    """测试 Vue 文件的正则表达式信息提取"""
    
    # 模拟包含可提取信息但 JSON 格式错误的响应
    extractable_response = '''
    Review for Vue component:
    
    "overall_score": 82,
    "code_quality_score": 85,
    "security_score": 80,
    
    Found issues:
    "title": "Component lifecycle",
    "description": "Consider using onMounted instead of mounted",
    
    "title": "Props validation",
    "description": "Add proper prop types",
    
    "positive_points": ["Good template structure", "Clear component logic"],
    
    "summary": "Well-structured Vue component with minor improvements needed"
    '''
    
    test_file = FileInfo(filename="components/UserProfile.vue")
    
    result = _parse_single_file_response(extractable_response, test_file)
    
    # 验证信息提取（可能通过正则表达式或默认处理）
    assert result["filename"] == "components/UserProfile.vue"
    assert isinstance(result["score"], int)
    assert isinstance(result["issues"], list)
    assert isinstance(result["positive_points"], list)
    assert isinstance(result["summary"], str)

    # 验证提取的具体值
    assert result["score"] == 82  # 从 overall_score 映射而来
    assert result["code_quality_score"] == 85
    assert result["security_score"] == 80
    assert len(result["issues"]) >= 1
    assert "Good template structure" in result["positive_points"]


if __name__ == "__main__":
    test_vue_file_json_parsing_error()
    test_vue_file_with_multiple_json_errors()
    test_vue_file_completely_malformed()
    test_vue_file_with_regex_extraction()
    print("所有 Vue 文件解析测试通过！")
