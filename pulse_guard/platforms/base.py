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

    def post_pr_comments_batch(self, repo: str, pr_number: int, comment: str, max_length: int = 4000) -> List[Dict[str, Any]]:
        """分批发布 Pull Request 评论

        如果评论内容超过长度限制，会自动分割成多个评论发布

        Args:
            repo: 仓库名称，格式为 "owner/repo"
            pr_number: Pull Request 编号
            comment: 评论内容
            max_length: 单个评论的最大长度，默认4000字符

        Returns:
            评论信息字典列表
        """
        if len(comment) <= max_length:
            # 如果评论长度在限制内，直接发布
            return [self.post_pr_comment(repo, pr_number, comment)]

        # 分割评论内容
        comment_parts = self._split_comment(comment, max_length)
        results = []

        for i, part in enumerate(comment_parts):
            # 为每个部分添加序号标识
            if len(comment_parts) > 1:
                part_with_header = f"**📝 代码审查报告 ({i+1}/{len(comment_parts)})**\n\n{part}"
            else:
                part_with_header = part

            try:
                result = self.post_pr_comment(repo, pr_number, part_with_header)
                results.append(result)
            except Exception as e:
                # 如果某个部分发布失败，记录错误但继续发布其他部分
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"发布评论部分 {i+1} 失败: {e}")
                results.append({"error": str(e), "part": i+1})

        return results

    def _split_comment(self, comment: str, max_length: int) -> List[str]:
        """智能分割评论内容

        Args:
            comment: 原始评论内容
            max_length: 最大长度

        Returns:
            分割后的评论列表
        """
        if len(comment) <= max_length:
            return [comment]

        parts = []
        lines = comment.split('\n')
        current_part = ""

        for line in lines:
            # 检查添加这一行是否会超出限制
            test_part = current_part + ('\n' if current_part else '') + line

            if len(test_part) <= max_length - 100:  # 预留100字符给头部信息
                current_part = test_part
            else:
                # 如果当前部分不为空，保存它
                if current_part:
                    parts.append(current_part)
                    current_part = line
                else:
                    # 如果单行就超过限制，强制截断
                    if len(line) > max_length - 100:
                        # 按字符截断
                        chunk_size = max_length - 100
                        for i in range(0, len(line), chunk_size):
                            chunk = line[i:i + chunk_size]
                            if i + chunk_size < len(line):
                                chunk += "..."
                            parts.append(chunk)
                    else:
                        current_part = line

        # 添加最后一部分
        if current_part:
            parts.append(current_part)

        return parts

    def get_platform_name(self) -> str:
        """获取平台名称
        
        Returns:
            平台名称
        """
        return self.platform_name
