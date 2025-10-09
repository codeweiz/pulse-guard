"""代码审查服务"""
import asyncio
import logging
from typing import Dict, List, Any

from backend.llm.client import get_llm
from backend.models.workflow import AgentState, FileInfo, PRInfo, FileReviewInfo, EnhancedAnalysis
from backend.agent.config.prompts import review_prompts
from backend.agent.config.review_config import review_config
from backend.agent.utils.validators import validator
from backend.agent.utils.parsers import parser

logger = logging.getLogger(__name__)


class ReviewService:
    """代码审查服务"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def intelligent_code_review(self, state: AgentState) -> AgentState:
        """智能代码审查"""
        pr_info = state.pr_info
        files = state.files

        if not files:
            return self._create_empty_review_state(state)

        self.logger.info(f"开始并发审查 {len(files)} 个代码文件")

        try:
            # 并发审查所有文件
            file_reviews = await self._review_files_concurrently(files, pr_info)

            # 计算总体评分
            overall_result = self._calculate_overall_scores(file_reviews)

            # 创建增强分析结果
            enhanced_analysis = self._create_enhanced_analysis(overall_result, file_reviews)

            # 更新状态
            new_state = state.model_copy()
            new_state.file_reviews = file_reviews
            new_state.overall_summary = overall_result.get("summary", "并发审查完成")
            new_state.enhanced_analysis = enhanced_analysis

            return new_state

        except Exception as e:
            self.logger.error(f"并发审查失败: {e}")
            return state

    def _create_empty_review_state(self, state: AgentState) -> AgentState:
        """创建空审查状态"""
        self.logger.warning("没有代码文件需要审查")

        new_state = state.model_copy()
        new_state.file_reviews = []
        new_state.overall_summary = "没有代码文件需要审查"
        new_state.enhanced_analysis = EnhancedAnalysis(
            overall_score=100,
            code_quality_score=100,
            security_score=100,
            business_score=100,
            file_results=[],
            summary="没有代码文件需要审查",
        )
        return new_state

    async def _review_files_concurrently(
            self,
            files: List[FileInfo],
            pr_info: PRInfo
    ) -> List[FileReviewInfo]:
        """并发审查文件"""
        self.logger.info(f"使用 asyncio.gather 并发处理 {len(files)} 个文件")

        # 创建所有文件审查任务
        tasks = [self._review_single_file_async(file, pr_info) for file in files]

        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        file_reviews = []
        for file, result in zip(files, results):
            if isinstance(result, Exception):
                self.logger.error(f"文件 {file.filename} 审查异常: {result}")
                file_review = self._create_error_review(file.filename, str(result))
            else:
                file_review = self._convert_result_to_file_review(result, file.filename)

            file_reviews.append(file_review)
            self.logger.info(f"文件 {file.filename} 审查完成")

        return file_reviews

    async def _review_single_file_async(self, file: FileInfo, pr_info: PRInfo) -> Dict[str, Any]:
        """异步审查单个文件"""
        try:
            llm = get_llm()

            # 构建审查提示
            prompt = self._build_single_file_review_prompt(file, pr_info)

            # 异步调用LLM
            response = await llm.ainvoke(prompt)
            review_content = str(
                response.content if hasattr(response, "content") else response
            )

            # 解析审查结果
            return parser.parse_single_file_response(review_content, file)

        except Exception as e:
            self.logger.error(f"单文件审查失败 {file.filename}: {e}")
            return validator.create_default_file_review(file.filename, str(e))

    def _build_single_file_review_prompt(self, file: FileInfo, pr_info: PRInfo) -> str:
        """构建单文件审查提示"""
        patch = validator.safe_get_string(file.patch)
        content = validator.safe_get_string(file.content)

        # 限制内容长度
        patch_limit = review_config.FILE_CONTENT_LIMITS["patch_max_length"]
        content_limit = review_config.FILE_CONTENT_LIMITS["content_max_length"]

        truncated_patch = patch[:patch_limit] + ('...' if len(patch) > patch_limit else '')
        truncated_content = content[:content_limit] + ('...' if len(content) > content_limit else '')

        return review_prompts.SINGLE_FILE_REVIEW_TEMPLATE.format(
            pr_title=validator.safe_get_string(pr_info.title),
            pr_author=validator.safe_get_user_login(pr_info),
            filename=file.filename,
            status=file.status,
            additions=file.additions,
            deletions=file.deletions,
            patch=truncated_patch,
            content=truncated_content,
        )

    def _create_error_review(self, filename: str, error_msg: str) -> FileReviewInfo:
        """创建错误审查结果"""
        return FileReviewInfo(
            filename=filename,
            score=70,
            issues=[],
            positive_points=[],
            summary=f"审查失败: {error_msg}",
        )

    def _convert_result_to_file_review(self, result: Dict[str, Any], filename: str) -> FileReviewInfo:
        """转换结果为FileReviewInfo"""
        if isinstance(result, dict):
            # 转换问题列表
            issues = []
            for issue_data in result.get("issues", []):
                try:
                    from backend.models.workflow import CodeIssueInfo
                    issue = CodeIssueInfo(**validator.validate_issue_data(issue_data))
                    issues.append(issue)
                except Exception as e:
                    self.logger.warning(f"转换问题信息失败: {e}")
                    continue

            return FileReviewInfo(
                filename=result.get("filename", filename),
                score=result.get("score", 80),
                code_quality_score=result.get("code_quality_score", 80),
                security_score=result.get("security_score", 80),
                business_score=result.get("business_score", 80),
                performance_score=result.get("performance_score", 80),
                best_practices_score=result.get("best_practices_score", 80),
                issues=issues,
                positive_points=result.get("positive_points", []),
                summary=result.get("summary", ""),
            )
        else:
            return self._create_error_review(filename, "审查结果解析异常")

    def _calculate_overall_scores(self, file_reviews: List[FileReviewInfo]) -> Dict[str, Any]:
        """计算总体评分"""
        if not file_reviews:
            return {
                "overall_score": 100,
                "code_quality_score": 100,
                "security_score": 100,
                "business_score": 100,
                "summary": "没有文件需要审查",
                "standards_passed": 0,
                "standards_failed": 0,
                "standards_total": 0,
            }

        total_files = len(file_reviews)

        # 计算各维度平均分
        avg_scores = {}
        for score_type in ["code_quality_score", "security_score", "business_score",
                           "performance_score", "best_practices_score"]:
            avg_scores[score_type] = sum(
                getattr(fr, score_type, 80) for fr in file_reviews
            ) / total_files

        # 计算总体评分（加权平均）
        weights = review_config.SCORE_WEIGHTS
        overall_score = (
                avg_scores["code_quality_score"] * weights["code_quality"] +
                avg_scores["security_score"] * weights["security"] +
                avg_scores["business_score"] * weights["business"] +
                avg_scores["performance_score"] * weights["performance"] +
                avg_scores["best_practices_score"] * weights["best_practices"]
        )

        # 统计问题数量
        total_issues = sum(len(fr.issues) for fr in file_reviews)
        high_score_files = sum(1 for fr in file_reviews if fr.score >= 85)

        return {
            "overall_score": round(overall_score, 1),
            **{k: round(v, 1) for k, v in avg_scores.items()},
            "summary": f"审查了 {total_files} 个文件，发现 {total_issues} 个问题，{high_score_files} 个文件质量优秀",
            "standards_passed": max(0, total_files * 5 - total_issues),
            "standards_failed": total_issues,
            "standards_total": total_files * 5,
        }

    def _create_enhanced_analysis(
            self,
            overall_result: Dict[str, Any],
            file_reviews: List[FileReviewInfo]
    ) -> EnhancedAnalysis:
        """创建增强分析结果"""
        return EnhancedAnalysis(
            overall_score=overall_result.get("overall_score", 80),
            code_quality_score=overall_result.get("code_quality_score", 80),
            security_score=overall_result.get("security_score", 80),
            business_score=overall_result.get("business_score", 80),
            file_results=file_reviews,
            summary=overall_result.get("summary", "并发审查完成"),
            standards_passed=overall_result.get("standards_passed", 0),
            standards_failed=overall_result.get("standards_failed", 0),
            standards_total=overall_result.get("standards_total", 0),
        )


# 全局审查服务实例
review_service = ReviewService()
