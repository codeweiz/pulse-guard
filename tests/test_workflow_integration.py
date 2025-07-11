"""
测试工作流集成，验证类型修复后的完整功能
"""

import pytest
from unittest.mock import Mock, patch
from pulse_guard.agent.graph import (
    build_code_review_graph,
    fetch_pr_and_code_files,
    intelligent_code_review,
    generate_summary,
    post_review_comment
)
from pulse_guard.models.workflow import (
    AgentState, 
    PRInfo, 
    UserInfo, 
    FileInfo,
    FileReviewInfo,
    CodeIssueInfo,
    EnhancedAnalysis
)


def test_fetch_pr_and_code_files_state_handling():
    """测试 fetch_pr_and_code_files 函数的状态处理"""
    # 创建测试状态
    test_pr_info = PRInfo(
        repo="test/repo",
        number=1,
        platform="github",
        author=UserInfo(login="testuser")
    )
    
    test_state = AgentState(pr_info=test_pr_info)
    
    # Mock 平台提供者
    with patch('pulse_guard.agent.graph.get_platform_provider') as mock_provider:
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
        mock_provider_instance.get_file_content.return_value = 'test content'
        mock_provider.return_value = mock_provider_instance
        
        # 执行函数
        result_state = fetch_pr_and_code_files(test_state)
        
        # 验证结果状态类型
        assert isinstance(result_state, AgentState)
        assert isinstance(result_state.pr_info, PRInfo)
        assert isinstance(result_state.files, list)
        assert isinstance(result_state.file_contents, dict)
        assert isinstance(result_state.file_reviews, list)
        
        # 验证状态内容
        assert result_state.pr_info.title == 'Test PR'
        assert len(result_state.files) == 1
        assert result_state.files[0].filename == 'test.py'
        assert 'test.py' in result_state.file_contents


async def test_intelligent_code_review_state_handling():
    """测试 intelligent_code_review 函数的状态处理"""
    # 创建测试状态
    test_pr_info = PRInfo(
        repo="test/repo",
        number=1,
        platform="github",
        author=UserInfo(login="testuser")
    )

    test_file = FileInfo(
        filename="test.py",
        status="modified",
        content="print('hello')"
    )

    test_state = AgentState(
        pr_info=test_pr_info,
        files=[test_file]
    )

    # 测试空文件情况
    empty_state = AgentState(
        pr_info=test_pr_info,
        files=[]
    )

    result_state = await intelligent_code_review(empty_state)

    # 验证结果状态类型
    assert isinstance(result_state, AgentState)
    assert isinstance(result_state.file_reviews, list)
    assert isinstance(result_state.enhanced_analysis, EnhancedAnalysis)
    assert result_state.overall_summary == "没有代码文件需要审查"


def test_generate_summary_state_handling():
    """测试 generate_summary 函数的状态处理"""
    # 创建测试状态
    test_pr_info = PRInfo(
        repo="test/repo",
        number=1,
        platform="github",
        author=UserInfo(login="testuser")
    )
    
    # 测试有增强分析的情况
    enhanced_analysis = EnhancedAnalysis(
        overall_score=85.0,
        summary="Test analysis summary"
    )
    
    test_state = AgentState(
        pr_info=test_pr_info,
        enhanced_analysis=enhanced_analysis
    )
    
    result_state = generate_summary(test_state)
    
    # 验证结果状态类型
    assert isinstance(result_state, AgentState)
    assert result_state.overall_summary == "Test analysis summary"


def test_post_review_comment_state_handling():
    """测试 post_review_comment 函数的状态处理"""
    # 创建测试状态
    test_pr_info = PRInfo(
        repo="test/repo",
        number=1,
        platform="github",
        author=UserInfo(login="testuser"),
        repo_full_name="test/repo"
    )
    
    test_file_review = FileReviewInfo(
        filename="test.py",
        score=85,
        summary="Good code quality"
    )
    
    test_state = AgentState(
        pr_info=test_pr_info,
        file_reviews=[test_file_review],
        overall_summary="Overall good"
    )
    
    # Mock 平台提供者和数据库
    with patch('pulse_guard.agent.graph.get_platform_provider') as mock_provider, \
         patch('pulse_guard.database.DatabaseManager') as mock_db:
        
        mock_provider_instance = Mock()
        mock_provider_instance.post_pr_comments_batch.return_value = [{"success": True}]
        mock_provider.return_value = mock_provider_instance
        
        mock_db.save_complete_review_result.return_value = 123
        
        # 执行函数
        result_state = post_review_comment(test_state)
        
        # 验证结果状态类型
        assert isinstance(result_state, AgentState)
        # 函数应该返回原状态（可能有修改）
        assert result_state.pr_info.repo == "test/repo"


def test_graph_compilation():
    """测试图编译和基本执行"""
    graph = build_code_review_graph()
    
    # 验证图可以正常编译
    assert graph is not None
    
    # 验证图的基本结构
    # 注意：这里我们不执行完整的图，因为需要真实的外部依赖


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        test_fetch_pr_and_code_files_state_handling()
        await test_intelligent_code_review_state_handling()
        test_generate_summary_state_handling()
        test_post_review_comment_state_handling()
        test_graph_compilation()
        print("所有集成测试通过！")

    asyncio.run(run_tests())
