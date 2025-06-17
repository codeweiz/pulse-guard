"""
平台提供者基类和接口定义。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class PlatformProvider(ABC):
    """平台提供者抽象基类
    
    定义了所有代码托管平台需要实现的通用接口。
    """

    def __init__(self, platform_name: str):
        """初始化平台提供者
        
        Args:
            platform_name: 平台名称，如 "github", "gitee"
        """
        self.platform_name = platform_name

    @abstractmethod
    def get_pr_info(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """获取 Pull Request 基本信息
        
        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号
            
        Returns:
            Pull Request 信息字典，包含以下字段：
            - number: PR 编号
            - title: PR 标题
            - body: PR 描述
            - state: PR 状态
            - user: 创建者用户名
            - html_url: PR 页面链接
            - created_at: 创建时间 (ISO格式字符串)
            - updated_at: 更新时间 (ISO格式字符串)
            - head_sha: 头部提交 SHA
            - base_sha: 基础提交 SHA
            - repo_full_name: 完整仓库名称
        """
        pass

    @abstractmethod
    def get_pr_files(self, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """获取 Pull Request 修改的文件列表
        
        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号
            
        Returns:
            文件列表，每个文件包含以下字段：
            - filename: 文件名
            - status: 文件状态 (added, modified, removed, renamed)
            - additions: 新增行数
            - deletions: 删除行数
            - changes: 总变更行数
            - patch: 变更补丁内容
        """
        pass

    @abstractmethod
    def get_file_content(self, repo: str, file_path: str, ref: str) -> str:
        """获取文件内容
        
        Args:
            repo: 仓库名称，格式为 "owner/repo"
            file_path: 文件路径
            ref: 分支、标签或提交 SHA
            
        Returns:
            文件内容字符串
        """
        pass

    @abstractmethod
    def post_pr_comment(self, repo: str, pr_number: int, comment: str) -> Dict[str, Any]:
        """发布 Pull Request 评论
        
        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号
            comment: 评论内容
            
        Returns:
            评论信息字典
        """
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """验证 Webhook 签名
        
        Args:
            payload: 请求体字节数据
            signature: 签名字符串
            
        Returns:
            是否验证通过
        """
        pass

    def get_platform_name(self) -> str:
        """获取平台名称
        
        Returns:
            平台名称
        """
        return self.platform_name
