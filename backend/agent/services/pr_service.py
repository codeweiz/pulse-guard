"""PR相关服务"""
import logging
from typing import Dict, List, Any

from backend.models.workflow import AgentState, FileInfo, PRInfo
from backend.platforms import get_platform_provider
from backend.utils.file_type_utils import is_code_file
from backend.agent.utils.validators import validator

logger = logging.getLogger(__name__)


class PRService:
    """PR服务类"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def fetch_pr_and_code_files(self, state: AgentState) -> AgentState:
        """获取PR信息和代码文件内容"""
        pr_info = state.pr_info
        platform = pr_info.platform
        
        try:
            # 获取平台提供者
            provider = get_platform_provider(platform)
            
            # 获取PR详细信息
            pr_details = provider.get_pr_info(pr_info.repo, pr_info.number)
            updated_pr_info = self._update_pr_info(pr_info, pr_details)
            
            # 获取文件列表
            all_files = provider.get_pr_files(pr_info.repo, pr_info.number)
            file_infos = self._convert_to_file_infos(all_files)
            
            # 过滤代码文件
            code_files = [f for f in file_infos if is_code_file(f.filename)]
            
            self.logger.info(
                f"总文件数: {len(all_files)}, 有效文件数: {len(file_infos)}, 代码文件数: {len(code_files)}"
            )
            
            # 获取文件内容
            enhanced_files, file_contents = self._fetch_file_contents(
                code_files, provider, updated_pr_info
            )
            
            # 更新状态
            new_state = state.model_copy()
            new_state.pr_info = updated_pr_info
            new_state.files = enhanced_files
            new_state.file_contents = file_contents
            new_state.current_file_index = 0
            new_state.file_reviews = []
            
            return new_state
            
        except Exception as e:
            self.logger.error(f"获取PR信息失败: {e}")
            raise
    
    def _update_pr_info(self, pr_info: PRInfo, pr_details: Dict[str, Any]) -> PRInfo:
        """更新PR信息"""
        # 移除可能冲突的字段
        safe_pr_details = {
            k: v for k, v in pr_details.items()
            if k not in ['repo', 'number', 'platform', 'author']
        }
        
        return PRInfo(
            repo=pr_info.repo,
            number=pr_info.number,
            platform=pr_info.platform,
            author=pr_info.author,
            **safe_pr_details
        )
    
    def _convert_to_file_infos(self, all_files: List[Dict[str, Any]]) -> List[FileInfo]:
        """转换为FileInfo模型"""
        file_infos = []
        for file_data in all_files:
            try:
                file_info = validator.validate_file_info(file_data)
                file_infos.append(file_info)
            except Exception as e:
                self.logger.warning(f"跳过无效文件数据: {e}")
                continue
        return file_infos
    
    def _fetch_file_contents(
        self, 
        code_files: List[FileInfo], 
        provider: Any, 
        pr_info: PRInfo
    ) -> tuple[List[FileInfo], Dict[str, str]]:
        """获取文件内容"""
        file_contents = {}
        enhanced_files = []
        
        for file in code_files:
            if file.status != "removed":
                try:
                    content = provider.get_file_content(
                        pr_info.repo_full_name,
                        file.filename,
                        pr_info.head_sha,
                    )
                    file_contents[file.filename] = content
                    file.content = content
                except Exception as e:
                    error_msg = f"Error fetching file content: {str(e)}"
                    file_contents[file.filename] = error_msg
                    file.content = error_msg
                    self.logger.warning(f"获取文件内容失败 {file.filename}: {e}")
            
            enhanced_files.append(file)
        
        return enhanced_files, file_contents


# 全局PR服务实例
pr_service = PRService()
