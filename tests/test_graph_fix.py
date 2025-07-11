"""
测试 graph.py 中的类型修复
"""

import pytest
from pulse_guard.agent.graph import build_code_review_graph
from pulse_guard.models.workflow import AgentState, PRInfo, UserInfo


def test_graph_state_type():
    """测试图状态类型是否正确"""
    # 构建图
    graph = build_code_review_graph()
    
    # 验证图可以正常创建
    assert graph is not None
    
    # 创建测试状态
    test_pr_info = PRInfo(
        repo="test/repo",
        number=1,
        platform="github",
        author=UserInfo(login="testuser")
    )
    
    test_state = AgentState(pr_info=test_pr_info)
    
    # 验证状态具有所需的属性
    assert hasattr(test_state, 'file_reviews')
    assert hasattr(test_state, 'pr_info')
    assert hasattr(test_state, 'files')
    assert hasattr(test_state, 'file_contents')
    assert hasattr(test_state, 'enhanced_analysis')
    
    # 验证属性类型
    assert isinstance(test_state.file_reviews, list)
    assert isinstance(test_state.pr_info, PRInfo)
    assert isinstance(test_state.files, list)
    assert isinstance(test_state.file_contents, dict)


def test_agent_state_model_copy():
    """测试 AgentState 的 model_copy 方法"""
    test_pr_info = PRInfo(
        repo="test/repo",
        number=1,
        platform="github",
        author=UserInfo(login="testuser")
    )
    
    original_state = AgentState(pr_info=test_pr_info)
    
    # 测试 model_copy
    copied_state = original_state.model_copy()
    
    # 验证复制成功
    assert copied_state is not original_state
    assert copied_state.pr_info.repo == original_state.pr_info.repo
    assert copied_state.pr_info.number == original_state.pr_info.number
    
    # 验证可以修改复制的状态
    copied_state.overall_summary = "Test summary"
    assert copied_state.overall_summary == "Test summary"
    assert original_state.overall_summary is None


if __name__ == "__main__":
    test_graph_state_type()
    test_agent_state_model_copy()
    print("所有测试通过！")
