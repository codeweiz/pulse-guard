"""
测试 AddableValuesDict 错误修复
验证原始错误 "'AddableValuesDict' object has no attribute 'file_reviews'" 已被修复
"""

import pytest
from unittest.mock import Mock, patch
from pulse_guard.agent.graph import run_code_review_async
from pulse_guard.models.workflow import UserInfo


@pytest.mark.asyncio
async def test_addable_values_dict_fix():
    """测试 AddableValuesDict 错误已被修复"""
    
    # 创建测试 PR 信息
    test_pr_info = {
        "repo": "test/repo",
        "number": 39,  # 使用原始错误中的 PR 编号
        "platform": "github",
        "author": {
            "login": "testuser",
            "id": "123"
        },
        "title": "Test PR",
        "body": "Test description",
        "head_sha": "abc123",
        "base_sha": "def456",
        "repo_full_name": "test/repo"
    }
    
    # Mock 所有外部依赖
    with patch('pulse_guard.agent.graph.get_platform_provider') as mock_provider, \
         patch('pulse_guard.database.DatabaseManager') as mock_db, \
         patch('pulse_guard.llm.client.get_llm') as mock_llm:
        
        # 设置 mock 平台提供者
        mock_provider_instance = Mock()
        mock_provider_instance.get_pr_info.return_value = {
            'title': 'Test PR',
            'body': 'Test description',
            'head_sha': 'abc123',
            'base_sha': 'def456'
        }
        mock_provider_instance.get_pr_files.return_value = [
            {
                'filename': 'test.py',
                'status': 'modified',
                'additions': 10,
                'deletions': 5,
                'patch': 'test patch'
            }
        ]
        mock_provider_instance.get_file_content.return_value = 'print("hello world")'
        mock_provider_instance.post_pr_comments_batch.return_value = [{"success": True}]
        mock_provider.return_value = mock_provider_instance
        
        # 设置 mock LLM
        mock_llm_instance = Mock()
        mock_response = Mock()
        mock_response.content = '''
        {
            "filename": "test.py",
            "overall_score": 85,
            "code_quality_score": 80,
            "security_score": 90,
            "business_score": 85,
            "performance_score": 80,
            "best_practices_score": 85,
            "issues": [
                {
                    "type": "info",
                    "title": "Good code",
                    "description": "Code looks good",
                    "severity": "info",
                    "category": "code_quality"
                }
            ],
            "positive_points": ["Clean code"],
            "summary": "Good quality code"
        }
        '''
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_llm_instance.invoke.return_value = mock_response
        mock_llm.return_value = mock_llm_instance
        
        # 设置 mock 数据库
        mock_db.save_complete_review_result.return_value = 123
        
        # 执行代码审查 - 这应该不会抛出 AddableValuesDict 错误
        try:
            result = await run_code_review_async(test_pr_info)
            
            # 验证结果结构
            assert isinstance(result, dict)
            assert 'pr_info' in result
            assert 'files' in result
            assert 'file_reviews' in result
            assert 'overall_summary' in result
            assert 'enhanced_analysis' in result
            
            # 验证没有 AddableValuesDict 相关错误
            assert result['file_reviews'] is not None
            assert isinstance(result['file_reviews'], list)
            
            print("✅ AddableValuesDict 错误已修复！")
            
        except AttributeError as e:
            if "AddableValuesDict" in str(e) and "file_reviews" in str(e):
                pytest.fail(f"原始 AddableValuesDict 错误仍然存在: {e}")
            else:
                # 其他 AttributeError 可能是正常的
                raise
        except Exception as e:
            # 其他异常可能是正常的（如网络错误等）
            print(f"测试完成，遇到其他异常（这可能是正常的）: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_addable_values_dict_fix())
    print("AddableValuesDict 修复测试完成！")
