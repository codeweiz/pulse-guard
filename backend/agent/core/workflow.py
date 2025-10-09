"""代码审查工作流核心类"""
import asyncio
import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from backend.models.workflow import AgentState, PRInfo, UserInfo
from backend.agent.services.pr_service import pr_service
from backend.agent.services.review_service import review_service
from backend.agent.services.comment_service import comment_service

logger = logging.getLogger(__name__)


class CodeReviewWorkflow:
    """代码审查工作流"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.pr_service = pr_service
        self.review_service = review_service
        self.comment_service = comment_service
    
    def build_graph(self) -> Any:
        """构建LangGraph工作流图"""
        workflow = StateGraph(AgentState)
        
        # 添加节点
        workflow.add_node("fetch_pr_and_code_files", self._fetch_pr_and_code_files_wrapper)
        workflow.add_node("intelligent_code_review", self._intelligent_code_review_wrapper)
        workflow.add_node("post_review_comment", self._post_review_comment_wrapper)
        
        # 添加边
        workflow.add_edge("fetch_pr_and_code_files", "intelligent_code_review")
        workflow.add_edge("intelligent_code_review", "post_review_comment")
        workflow.add_edge("post_review_comment", END)
        
        # 设置入口点
        workflow.set_entry_point("fetch_pr_and_code_files")
        
        return workflow.compile()
    
    def _fetch_pr_and_code_files_wrapper(self, state: AgentState) -> AgentState:
        """获取PR信息和代码文件的包装器"""
        try:
            return self.pr_service.fetch_pr_and_code_files(state)
        except Exception as e:
            self.logger.error(f"获取PR信息失败: {e}")
            raise
    
    async def _intelligent_code_review_wrapper(self, state: AgentState) -> AgentState:
        """智能代码审查的包装器"""
        try:
            return await self.review_service.intelligent_code_review(state)
        except Exception as e:
            self.logger.error(f"代码审查失败: {e}")
            return state
    
    def _post_review_comment_wrapper(self, state: AgentState) -> AgentState:
        """发布审查评论的包装器"""
        try:
            return self.comment_service.post_review_comment(state)
        except Exception as e:
            self.logger.error(f"发布评论失败: {e}")
            return state
    
    async def run_async(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """异步运行代码审查工作流"""
        try:
            # 构建工作流图
            graph = self.build_graph()
            
            # 创建初始状态
            initial_state = self._create_initial_state(pr_info)
            
            # 执行工作流
            result = await graph.ainvoke(initial_state)
            
            # 转换结果为字典格式
            return self._convert_state_to_dict(result)
            
        except Exception as e:
            self.logger.error(f"工作流执行失败: {e}")
            raise
    
    def run_sync(self, pr_info: Dict[str, Any]) -> Dict[str, Any]:
        """同步运行代码审查工作流"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用线程池
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.run_async(pr_info))
                    return future.result()
            else:
                return loop.run_until_complete(self.run_async(pr_info))
        except RuntimeError:
            return asyncio.run(self.run_async(pr_info))
    
    def _create_initial_state(self, pr_info: Dict[str, Any]) -> AgentState:
        """创建初始状态"""
        # 解析作者信息
        author_data = pr_info.get("author", {})
        if isinstance(author_data, dict):
            author = UserInfo(**author_data)
        else:
            author = UserInfo(login="unknown")
        
        # 创建PR信息模型
        pr_info_model = PRInfo(
            repo=pr_info["repo"],
            number=pr_info["number"],
            platform=pr_info.get("platform", "github"),
            author=author,
            title=pr_info.get("title", ""),
            body=pr_info.get("body", ""),
            head_sha=pr_info.get("head_sha", ""),
            base_sha=pr_info.get("base_sha", ""),
            repo_full_name=pr_info.get("repo_full_name", pr_info["repo"])
        )
        
        return AgentState(pr_info=pr_info_model)
    
    def _convert_state_to_dict(self, state: Any) -> Dict[str, Any]:
        """将状态转换为字典格式"""
        # 处理LangGraph返回的状态
        if isinstance(state, dict):
            file_reviews_data = state.get("file_reviews", [])
            enhanced_analysis_data = state.get("enhanced_analysis")
            pr_info_data = state.get("pr_info", {})
            files_data = state.get("files", [])
            file_contents_data = state.get("file_contents", {})
            overall_summary_data = state.get("overall_summary")
            db_record_id_data = state.get("db_record_id")
        else:
            # AgentState对象
            file_reviews_data = state.file_reviews
            enhanced_analysis_data = state.enhanced_analysis
            pr_info_data = state.pr_info
            files_data = state.files
            file_contents_data = state.file_contents
            overall_summary_data = state.overall_summary
            db_record_id_data = state.db_record_id
        
        # 转换文件审查结果
        file_reviews = []
        for review in file_reviews_data:
            if hasattr(review, 'model_dump'):
                file_reviews.append(review.model_dump())
            else:
                file_reviews.append(review)
        
        # 转换增强分析数据
        enhanced_analysis = None
        if enhanced_analysis_data:
            if hasattr(enhanced_analysis_data, 'model_dump'):
                enhanced_analysis = enhanced_analysis_data.model_dump()
            else:
                enhanced_analysis = enhanced_analysis_data
        
        # 转换PR信息
        if hasattr(pr_info_data, 'model_dump'):
            pr_info_dict = pr_info_data.model_dump()
        else:
            pr_info_dict = pr_info_data
        
        # 转换文件数据
        files_list = []
        for f in files_data:
            if hasattr(f, 'model_dump'):
                files_list.append(f.model_dump())
            else:
                files_list.append(f)
        
        return {
            "pr_info": pr_info_dict,
            "files": files_list,
            "file_contents": file_contents_data,
            "file_reviews": file_reviews,
            "overall_summary": overall_summary_data,
            "enhanced_analysis": enhanced_analysis,
            "db_record_id": db_record_id_data,
        }


# 全局工作流实例
code_review_workflow = CodeReviewWorkflow()
