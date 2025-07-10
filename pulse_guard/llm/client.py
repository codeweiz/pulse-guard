"""
LLM 客户端模块，负责与 LLM 服务交互。
"""
from typing import Optional

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from pulse_guard.config import config


def get_llm(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
) -> BaseChatModel:
    """获取 LLM 客户端

    Args:
        base_url: 基础 URL，默认使用配置中的值
        provider: LLM 提供者，默认使用配置中的值
        model_name: 模型名称，默认使用配置中的值
        api_key: API 密钥，默认使用配置中的值
        **kwargs: 其他参数

    Returns:
        LLM 客户端
    """
    provider = provider or config.llm.provider
    model_name = model_name or config.llm.model_name
    base_url = base_url or config.llm.base_url
    api_key = api_key or config.llm.api_key

    # 使用 LangChain 的工厂函数初始化 LLM
    return init_chat_model(
        model=model_name,
        model_provider=provider,
        api_key=api_key,
        base_url=base_url,
        **kwargs
    )
