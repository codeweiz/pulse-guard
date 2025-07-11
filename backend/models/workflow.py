"""
工作流数据模型定义
使用 Pydantic 规范化工作流中的所有数据结构
"""

from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field, field_validator, model_validator


class UserInfo(BaseModel):
    """用户信息模型"""

    login: str = Field(description="用户登录名")
    id: Optional[str] = Field(default="", description="用户ID")
    name: Optional[str] = Field(default="", description="用户真实姓名")
    email: Optional[str] = Field(default="", description="用户邮箱")
    type: str = Field(default="User", description="用户类型")
    avatar_url: Optional[str] = Field(default="", description="头像URL")

    @field_validator("id", mode="before")
    @classmethod
    def convert_id_to_string(cls, v):
        """将ID转换为字符串"""
        if v is None:
            return ""
        return str(v)


class PRInfo(BaseModel):
    """PR信息模型"""
    
    # 基本信息
    repo: str = Field(description="仓库名称，格式为 owner/repo")
    number: int = Field(description="PR编号")
    platform: str = Field(default="github", description="平台名称")
    
    # PR详细信息
    title: str = Field(default="", description="PR标题")
    body: str = Field(default="", description="PR描述")
    state: str = Field(default="open", description="PR状态")
    merged: bool = Field(default=False, description="是否已合并")
    
    # 用户信息
    author: UserInfo = Field(description="PR作者信息")
    
    # 技术信息
    head_sha: str = Field(default="", description="头部提交SHA")
    base_sha: str = Field(default="", description="基础提交SHA")
    repo_full_name: str = Field(default="", description="完整仓库名称")
    html_url: str = Field(default="", description="PR页面URL")
    
    # 时间信息
    created_at: Optional[str] = Field(default="", description="创建时间")
    updated_at: Optional[str] = Field(default="", description="更新时间")
    closed_at: Optional[str] = Field(default="", description="关闭时间")
    merged_at: Optional[str] = Field(default="", description="合并时间")
    
    @model_validator(mode='after')
    def set_repo_full_name(self):
        """如果repo_full_name为空，使用repo字段"""
        if not self.repo_full_name:
            self.repo_full_name = self.repo
        return self


class FileInfo(BaseModel):
    """文件信息模型"""

    filename: str = Field(description="文件名")
    status: str = Field(default="modified", description="文件状态：added, modified, removed")
    additions: int = Field(default=0, description="新增行数")
    deletions: int = Field(default=0, description="删除行数")
    changes: int = Field(default=0, description="总变更行数")
    patch: str = Field(default="", description="补丁内容")
    content: str = Field(default="", description="文件内容")

    @field_validator("additions", "deletions", mode="before")
    @classmethod
    def validate_numbers(cls, v):
        """处理可能为None的数字字段"""
        return v if v is not None else 0
    
    @field_validator("changes", mode="before")
    @classmethod
    def validate_changes(cls, v, info):
        """处理changes字段，如果为None或0则自动计算"""
        if v is None or v == 0:
            # 从其他字段计算
            if hasattr(info, 'data') and info.data:
                additions = info.data.get("additions", 0) or 0
                deletions = info.data.get("deletions", 0) or 0
                return additions + deletions
            return 0
        return v


class CodeIssueInfo(BaseModel):
    """代码问题信息模型"""
    
    type: str = Field(description="问题类型：error, warning, info")
    title: str = Field(description="问题标题")
    description: str = Field(description="问题描述")
    line: Optional[int] = Field(default=None, description="问题所在行号")
    suggestion: str = Field(default="", description="修复建议")
    category: str = Field(default="general", description="问题分类")
    severity: str = Field(default="medium", description="严重程度")


class FileReviewInfo(BaseModel):
    """文件审查结果模型"""
    
    filename: str = Field(description="文件名")
    score: int = Field(default=80, description="总体评分")
    code_quality_score: int = Field(default=80, description="代码质量评分")
    security_score: int = Field(default=80, description="安全性评分")
    business_score: int = Field(default=80, description="业务逻辑评分")
    performance_score: int = Field(default=80, description="性能评分")
    best_practices_score: int = Field(default=80, description="最佳实践评分")
    
    issues: List[CodeIssueInfo] = Field(default_factory=list, description="问题列表")
    positive_points: List[str] = Field(default_factory=list, description="积极点")
    summary: str = Field(default="", description="审查总结")


class EnhancedAnalysis(BaseModel):
    """增强分析结果模型"""
    
    overall_score: float = Field(default=80.0, description="总体评分")
    code_quality_score: float = Field(default=80.0, description="代码质量评分")
    security_score: float = Field(default=80.0, description="安全性评分")
    business_score: float = Field(default=80.0, description="业务逻辑评分")
    performance_score: float = Field(default=80.0, description="性能评分")
    best_practices_score: float = Field(default=80.0, description="最佳实践评分")
    
    file_results: List[FileReviewInfo] = Field(default_factory=list, description="文件审查结果")
    summary: str = Field(default="", description="总体总结")
    
    standards_passed: int = Field(default=0, description="通过的标准数")
    standards_failed: int = Field(default=0, description="失败的标准数")
    standards_total: int = Field(default=0, description="总标准数")


class AgentState(BaseModel):
    """Agent状态模型"""
    
    # 消息列表
    messages: List[Union[AIMessage, HumanMessage]] = Field(default_factory=list, description="消息列表")
    
    # 核心数据
    pr_info: PRInfo = Field(description="PR信息")
    files: List[FileInfo] = Field(default_factory=list, description="文件列表")
    file_contents: Dict[str, str] = Field(default_factory=dict, description="文件内容映射")
    
    # 处理状态
    current_file_index: int = Field(default=0, description="当前处理的文件索引")
    
    # 审查结果
    file_reviews: List[FileReviewInfo] = Field(default_factory=list, description="文件审查结果")
    overall_summary: Optional[str] = Field(default=None, description="总体总结")
    enhanced_analysis: Optional[EnhancedAnalysis] = Field(default=None, description="增强分析结果")
    
    # 数据库记录
    db_record_id: Optional[int] = Field(default=None, description="数据库记录ID")
    
    class Config:
        arbitrary_types_allowed = True  # 允许任意类型，用于支持LangChain消息类型


class WebhookEventInfo(BaseModel):
    """Webhook事件信息模型"""
    
    event_type: str = Field(description="事件类型")
    action: str = Field(description="事件动作")
    platform: str = Field(description="平台名称")
    
    # PR基本信息
    repo: str = Field(description="仓库名称")
    pr_number: int = Field(description="PR编号")
    
    # 作者信息
    author: UserInfo = Field(description="作者信息")
    
    # 原始数据
    raw_payload: Dict[str, Any] = Field(description="原始webhook载荷")


class WorkflowInput(BaseModel):
    """工作流输入模型"""
    
    repo: str = Field(description="仓库名称")
    number: int = Field(description="PR编号") 
    platform: str = Field(default="github", description="平台名称")
    author: Optional[UserInfo] = Field(default=None, description="作者信息")


class WorkflowOutput(BaseModel):
    """工作流输出模型"""
    
    status: str = Field(description="处理状态")
    pr_number: int = Field(description="PR编号")
    repo: str = Field(description="仓库名称")
    platform: str = Field(description="平台名称")
    
    file_count: int = Field(default=0, description="处理的文件数量")
    issue_count: int = Field(default=0, description="发现的问题数量")
    
    enhanced_analysis: Optional[EnhancedAnalysis] = Field(default=None, description="增强分析结果")
    error: Optional[str] = Field(default=None, description="错误信息")
