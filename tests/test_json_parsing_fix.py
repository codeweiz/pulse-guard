"""
测试 JSON 解析修复功能
验证对格式错误的 LLM 响应的处理能力
"""

import pytest
from pulse_guard.agent.graph import _parse_single_file_response, _fix_json_format, _extract_info_with_regex
from pulse_guard.models.workflow import FileInfo


def test_fix_json_format():
    """测试 JSON 格式修复功能"""
    
    # 测试缺少逗号的情况
    broken_json = '''
    {
        "filename": "test.py"
        "score": 85
        "issues": []
    }
    '''
    
    fixed_json = _fix_json_format(broken_json)
    
    # 应该能够成功解析
    import json
    try:
        result = json.loads(fixed_json)
        assert result["filename"] == "test.py"
        assert result["score"] == 85
    except json.JSONDecodeError:
        pytest.fail("JSON 修复失败")


def test_parse_malformed_json_response():
    """测试解析格式错误的 JSON 响应"""
    
    # 模拟 LLM 返回的格式错误的 JSON
    malformed_response = '''
    ```json
    {
        "filename": "test.vue",
        "overall_score": 85,
        "code_quality_score": 80
        "security_score": 90,
        "business_score": 85,
        "issues": [
            {
                "type": "warning",
                "title": "Missing semicolon"
                "description": "Line 26 missing semicolon",
                "severity": "warning",
                "category": "code_quality"
            }
        ],
        "positive_points": ["Good structure"],
        "summary": "Overall good code quality"
    ```
    '''
    
    test_file = FileInfo(filename="test.vue")
    
    # 应该能够处理格式错误的 JSON
    result = _parse_single_file_response(malformed_response, test_file)
    
    assert result["filename"] == "test.vue"
    assert isinstance(result["score"], int)
    assert isinstance(result["issues"], list)
    assert isinstance(result["positive_points"], list)
    assert isinstance(result["summary"], str)


def test_extract_info_with_regex():
    """测试正则表达式信息提取功能"""
    
    # 模拟完全无法解析的响应
    broken_response = '''
    This is a code review for test.py
    
    "overall_score": 75,
    "code_quality_score": 80,
    
    Issues found:
    "title": "Code smell",
    "description": "This code has issues",
    
    "positive_points": ["Good naming", "Clear structure"],
    
    "summary": "Code needs improvement"
    '''
    
    result = _extract_info_with_regex(broken_response, "test.py")
    
    assert result["filename"] == "test.py"
    assert result["overall_score"] == 75
    assert result["code_quality_score"] == 80
    assert len(result["issues"]) > 0
    assert result["issues"][0]["title"] == "Code smell"
    assert "Good naming" in result["positive_points"]


def test_parse_completely_broken_response():
    """测试处理完全损坏的响应"""
    
    broken_response = "This is not JSON at all! Just random text."
    
    test_file = FileInfo(filename="broken.js")
    
    # 应该返回默认结果而不是崩溃
    result = _parse_single_file_response(broken_response, test_file)

    assert result["filename"] == "broken.js"
    assert result["score"] == 75  # 默认分数
    assert isinstance(result["issues"], list)  # 应该是列表，可能为空


def test_parse_incomplete_json():
    """测试处理不完整的 JSON"""
    
    incomplete_json = '''
    {
        "filename": "incomplete.py",
        "overall_score": 85,
        "issues": [
            {
                "type": "warning",
                "title": "Incomplete
    '''
    
    test_file = FileInfo(filename="incomplete.py")
    
    # 应该能够处理不完整的 JSON
    result = _parse_single_file_response(incomplete_json, test_file)
    
    assert result["filename"] == "incomplete.py"
    assert isinstance(result["score"], int)


def test_parse_json_with_extra_commas():
    """测试处理多余逗号的 JSON"""
    
    json_with_extra_commas = '''
    {
        "filename": "extra.py",
        "overall_score": 85,
        "issues": [],
        "positive_points": ["Good code",],
        "summary": "Good work",
    }
    '''
    
    test_file = FileInfo(filename="extra.py")
    
    # 应该能够处理多余的逗号
    result = _parse_single_file_response(json_with_extra_commas, test_file)
    
    assert result["filename"] == "extra.py"
    assert result["score"] == 85
    assert "Good code" in result["positive_points"]


if __name__ == "__main__":
    test_fix_json_format()
    test_parse_malformed_json_response()
    test_extract_info_with_regex()
    test_parse_completely_broken_response()
    test_parse_incomplete_json()
    test_parse_json_with_extra_commas()
    print("所有 JSON 解析修复测试通过！")
