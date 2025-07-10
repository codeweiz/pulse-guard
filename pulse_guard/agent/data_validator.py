"""
数据验证和清理工具
处理来自不同平台的数据格式差异和类型问题
"""
import logging
from typing import Dict, Any, List, Union, Optional

logger = logging.getLogger(__name__)


class DataValidator:
    """数据验证和清理器"""

    @staticmethod
    def validate_pr_info(pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证和清理PR信息
        
        Args:
            pr_info: 原始PR信息
            
        Returns:
            清理后的PR信息
        """
        try:
            validated = {}

            # 基本字段
            validated['repo'] = DataValidator._safe_get_string(pr_info.get('repo', ''))
            validated['number'] = DataValidator._safe_get_int(pr_info.get('number', 0))
            validated['platform'] = DataValidator._safe_get_string(pr_info.get('platform', 'github'))

            # PR详细信息
            validated['title'] = DataValidator._safe_get_string(pr_info.get('title', ''))
            validated['body'] = DataValidator._safe_get_string(pr_info.get('body', ''))
            validated['head_sha'] = DataValidator._safe_get_string(pr_info.get('head_sha', ''))
            validated['repo_full_name'] = DataValidator._safe_get_string(
                pr_info.get('repo_full_name', pr_info.get('repo', ''))
            )

            # 用户信息处理
            validated['user'] = DataValidator._validate_user_info(pr_info.get('user'))

            # 状态信息
            validated['state'] = DataValidator._safe_get_string(pr_info.get('state', 'open'))
            validated['merged'] = DataValidator._safe_get_bool(pr_info.get('merged', False))

            # 时间信息
            validated['created_at'] = DataValidator._safe_get_string(pr_info.get('created_at', ''))
            validated['updated_at'] = DataValidator._safe_get_string(pr_info.get('updated_at', ''))

            logger.debug(f"PR信息验证完成: {validated['repo']}#{validated['number']}")
            return validated

        except Exception as e:
            logger.error(f"PR信息验证失败: {e}")
            # 返回最小可用的PR信息
            return {
                'repo': DataValidator._safe_get_string(pr_info.get('repo', '')),
                'number': DataValidator._safe_get_int(pr_info.get('number', 0)),
                'platform': DataValidator._safe_get_string(pr_info.get('platform', 'github')),
                'title': '未知标题',
                'body': '',
                'user': {'login': 'unknown'},
                'head_sha': '',
                'repo_full_name': DataValidator._safe_get_string(pr_info.get('repo', ''))
            }

    @staticmethod
    def validate_files_info(files: List[Any]) -> List[Dict[str, Any]]:
        """验证和清理文件信息
        
        Args:
            files: 原始文件信息列表
            
        Returns:
            清理后的文件信息列表
        """
        validated_files = []

        for file_data in files:
            try:
                if not isinstance(file_data, dict):
                    logger.warning(f"跳过非字典类型的文件数据: {type(file_data)}")
                    continue

                validated_file = {
                    'filename': DataValidator._safe_get_string(file_data.get('filename', '')),
                    'status': DataValidator._safe_get_string(file_data.get('status', 'modified')),
                    'additions': DataValidator._safe_get_int(file_data.get('additions', 0)),
                    'deletions': DataValidator._safe_get_int(file_data.get('deletions', 0)),
                    'changes': DataValidator._safe_get_int(file_data.get('changes', 0)),
                    'patch': DataValidator._safe_get_string(file_data.get('patch', '')),
                    'content': DataValidator._safe_get_string(file_data.get('content', ''))
                }

                # 如果changes为0，尝试计算
                if validated_file['changes'] == 0:
                    validated_file['changes'] = validated_file['additions'] + validated_file['deletions']

                # 只添加有效的文件
                if validated_file['filename']:
                    validated_files.append(validated_file)
                else:
                    logger.warning("跳过没有文件名的文件数据")

            except Exception as e:
                logger.error(f"验证文件信息失败: {e}")
                continue

        logger.debug(f"文件信息验证完成: {len(validated_files)} 个文件")
        return validated_files

    @staticmethod
    def _validate_user_info(user_data: Any) -> Dict[str, str]:
        """验证用户信息"""
        if isinstance(user_data, dict):
            return {
                'login': DataValidator._safe_get_string(user_data.get('login', 'unknown')),
                'id': DataValidator._safe_get_string(user_data.get('id', '')),
                'type': DataValidator._safe_get_string(user_data.get('type', 'User'))
            }
        elif isinstance(user_data, str):
            return {
                'login': user_data,
                'id': '',
                'type': 'User'
            }
        else:
            return {
                'login': 'unknown',
                'id': '',
                'type': 'User'
            }

    @staticmethod
    def _safe_get_string(value: Any, default: str = '') -> str:
        """安全地获取字符串值"""
        if value is None:
            return default
        try:
            return str(value).strip()
        except Exception:
            return default

    @staticmethod
    def _safe_get_int(value: Any, default: int = 0) -> int:
        """安全地获取整数值"""
        if value is None:
            return default
        try:
            if isinstance(value, (int, float)):
                return int(value)
            elif isinstance(value, str):
                return int(float(value.strip()))
            else:
                return default
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_get_bool(value: Any, default: bool = False) -> bool:
        """安全地获取布尔值"""
        if value is None:
            return default
        try:
            if isinstance(value, bool):
                return value
            elif isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(value, (int, float)):
                return bool(value)
            else:
                return default
        except Exception:
            return default


# 全局验证器实例
data_validator = DataValidator()
