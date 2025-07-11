"""响应解析工具"""
import json
import logging
import re
from typing import Any, Dict, Union

from backend.models.workflow import FileInfo
from backend.agent.config.review_config import review_config
from backend.agent.utils.validators import validator

logger = logging.getLogger(__name__)


class ResponseParser:
    """LLM响应解析器"""
    
    @staticmethod
    def parse_single_file_response(response: str, file: Union[FileInfo, Dict[str, Any]]) -> Dict[str, Any]:
        """解析单文件审查响应"""
        filename = file.filename if isinstance(file, FileInfo) else file.get("filename", "unknown")
        
        try:
            # 尝试提取JSON
            json_str = ResponseParser._extract_json_from_response(response)

            if json_str:
                # 清理和修复JSON格式
                json_str = ResponseParser._fix_json_format(json_str)

                # 尝试多种方式解析JSON
                result = ResponseParser._try_parse_json(json_str, filename)
                if result is None:
                    # JSON解析失败，使用正则表达式提取
                    logger.warning(f"JSON解析失败，使用正则表达式提取: {filename}")
                    result = ResponseParser._extract_info_with_regex(response, filename)
            else:
                # 使用正则表达式提取信息
                logger.warning(f"未找到JSON格式，使用正则表达式提取: {filename}")
                result = ResponseParser._extract_info_with_regex(response, filename)

            # 验证和标准化结果
            return ResponseParser._validate_and_normalize_result(result, filename)

        except Exception as e:
            logger.error(f"解析单文件响应失败 {filename}: {e}")
            return validator.create_default_file_review(filename, f"解析失败: {str(e)}")
    
    @staticmethod
    def _extract_json_from_response(response: str) -> str:
        """从响应中提取JSON字符串"""
        json_patterns = [
            r"```json\s*(.*?)\s*```",  # 标准 json 代码块
            r"```\s*(.*?)\s*```",      # 普通代码块
            r"\{.*\}",                 # 直接的 JSON 对象
        ]
        
        for pattern in json_patterns:
            json_match = re.search(pattern, response, re.DOTALL)
            if json_match:
                return json_match.group(1) if pattern != r"\{.*\}" else json_match.group(0)
        
        # 查找第一个{到最后一个}
        start = response.find("{")
        end = response.rfind("}") + 1
        if start != -1 and end > start:
            return response[start:end]
        
        return ""
    
    @staticmethod
    def _fix_json_format(json_str: str) -> str:
        """修复常见的JSON格式问题"""
        # 移除markdown标记
        json_str = re.sub(r'^```json\s*', '', json_str)
        json_str = re.sub(r'\s*```$', '', json_str)
        json_str = re.sub(r'^```\s*', '', json_str)

        # 修复字符串中的特殊字符
        # 转义字符串中的双引号（但不是JSON结构的双引号）
        json_str = re.sub(r'(?<=["\s])"(?=[^,}\]:]*[,}\]])(?![,}\]:]*")', '\\"', json_str)

        # 修复缺少逗号的问题
        json_str = re.sub(r'"\s*\n\s*"', '",\n    "', json_str)
        json_str = re.sub(r'(\d+)\s*\n\s*"', r'\1,\n    "', json_str)
        json_str = re.sub(r'(true|false)\s*\n\s*"', r'\1,\n    "', json_str)
        json_str = re.sub(r']\s*\n\s*"', '],\n    "', json_str)
        json_str = re.sub(r'}\s*\n\s*"', '},\n    "', json_str)

        # 修复多余的逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)

        # 修复字符串值中的换行符
        json_str = re.sub(r'(?<=: ")(.*?)(?="[,}])', lambda m: m.group(1).replace('\n', '\\n'), json_str, flags=re.DOTALL)

        # 修复不完整的JSON
        json_str = json_str.strip()
        if json_str.endswith(','):
            json_str = json_str[:-1]

        # 补全括号
        if json_str.count('{') > json_str.count('}'):
            json_str += '}' * (json_str.count('{') - json_str.count('}'))
        if json_str.count('[') > json_str.count(']'):
            json_str += ']' * (json_str.count('[') - json_str.count(']'))

        # 尝试修复常见的JSON语法错误
        # 修复缺少引号的键
        json_str = re.sub(r'(\w+):', r'"\1":', json_str)
        # 修复单引号
        json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)

        return json_str

    @staticmethod
    def _try_parse_json(json_str: str, filename: str) -> Dict[str, Any]:
        """尝试多种方式解析JSON"""
        # 方法1：直接解析
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"直接JSON解析失败 {filename}: {e}")

        # 方法2：尝试修复常见问题后解析
        try:
            # 移除可能的尾随逗号
            fixed_json = re.sub(r',(\s*[}\]])', r'\1', json_str)
            return json.loads(fixed_json)
        except json.JSONDecodeError as e:
            logger.debug(f"修复后JSON解析失败 {filename}: {e}")

        # 方法3：尝试提取部分有效的JSON
        try:
            # 查找最大的有效JSON片段
            for i in range(len(json_str), 0, -1):
                try:
                    partial_json = json_str[:i]
                    if partial_json.count('{') == partial_json.count('}'):
                        return json.loads(partial_json)
                except:
                    continue
        except Exception as e:
            logger.debug(f"部分JSON解析失败 {filename}: {e}")

        # 方法4：尝试使用ast.literal_eval（对于简单情况）
        try:
            import ast
            # 将JSON转换为Python字面量格式
            python_str = json_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            return ast.literal_eval(python_str)
        except Exception as e:
            logger.debug(f"AST解析失败 {filename}: {e}")

        return None

    @staticmethod
    def _extract_info_with_regex(response: str, filename: str) -> Dict[str, Any]:
        """使用正则表达式提取关键信息"""
        result = {
            "filename": filename,
            **review_config.DEFAULT_SCORES,
            "issues": [],
            "positive_points": [],
            "summary": f"文件 {filename} 审查完成（正则表达式解析）"
        }
        
        try:
            # 提取评分
            score_patterns = [
                (r'"overall_score":\s*(\d+)', 'overall_score'),
                (r'"code_quality_score":\s*(\d+)', 'code_quality_score'),
                (r'"security_score":\s*(\d+)', 'security_score'),
                (r'"business_score":\s*(\d+)', 'business_score'),
                (r'"performance_score":\s*(\d+)', 'performance_score'),
                (r'"best_practices_score":\s*(\d+)', 'best_practices_score'),
            ]
            
            for pattern, key in score_patterns:
                match = re.search(pattern, response)
                if match:
                    result[key] = int(match.group(1))
            
            # 提取总结
            summary_match = re.search(r'"summary":\s*"([^"]*)"', response)
            if summary_match:
                result["summary"] = summary_match.group(1)
            
            # 提取问题
            issue_pattern = r'"title":\s*"([^"]*)".*?"description":\s*"([^"]*)"'
            issue_matches = re.findall(issue_pattern, response, re.DOTALL)
            
            issues = []
            for title, description in issue_matches:
                issues.append({
                    "type": "info",
                    "title": title,
                    "description": description,
                    "severity": "info",
                    "category": "other",
                    "suggestion": ""
                })
            result["issues"] = issues
            
            # 提取积极点
            positive_pattern = r'"positive_points":\s*\[(.*?)\]'
            positive_match = re.search(positive_pattern, response, re.DOTALL)
            if positive_match:
                positive_content = positive_match.group(1)
                positive_points = re.findall(r'"([^"]*)"', positive_content)
                result["positive_points"] = positive_points
                
        except Exception as e:
            logger.warning(f"正则表达式提取失败: {e}")
        
        return result
    
    @staticmethod
    def _validate_and_normalize_result(result: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """验证和标准化结果"""
        # 验证问题列表
        validated_issues = []
        for issue in result.get("issues", []):
            if isinstance(issue, dict):
                validated_issues.append(validator.validate_issue_data(issue))
        
        # 构建标准化结果
        file_review = {
            "filename": filename,
            "score": validator.safe_get_score(result.get("overall_score", result.get("score", 80))),
            "code_quality_score": validator.safe_get_score(result.get("code_quality_score", 80)),
            "security_score": validator.safe_get_score(result.get("security_score", 80)),
            "business_score": validator.safe_get_score(result.get("business_score", 80)),
            "performance_score": validator.safe_get_score(result.get("performance_score", 80)),
            "best_practices_score": validator.safe_get_score(result.get("best_practices_score", 80)),
            "issues": validated_issues,
            "positive_points": result.get("positive_points", []),
            "summary": result.get("summary", f"文件 {filename} 审查完成"),
        }
        
        return file_review


# 全局解析器实例
parser = ResponseParser()
