"""
平台工厂模式实现。

提供平台提供者的自动注册和创建功能。
"""

import logging
from typing import Dict, Type

from .base import PlatformProvider

logger = logging.getLogger(__name__)


class PlatformFactory:
    """平台工厂类

    负责管理和创建不同平台的提供者实例。
    支持自动注册和动态创建平台提供者。
    """

    _providers: Dict[str, Type[PlatformProvider]] = {}
    _instances: Dict[str, PlatformProvider] = {}

    @classmethod
    def register(
        cls, platform_name: str, provider_class: Type[PlatformProvider]
    ) -> None:
        """注册平台提供者类

        Args:
            platform_name: 平台名称，如 "github", "gitee"
            provider_class: 平台提供者类
        """
        cls._providers[platform_name.lower()] = provider_class
        logger.info(
            f"Registered platform provider: {platform_name} -> {provider_class.__name__}"
        )

    @classmethod
    def create(cls, platform_name: str) -> PlatformProvider:
        """创建平台提供者实例

        Args:
            platform_name: 平台名称

        Returns:
            平台提供者实例

        Raises:
            ValueError: 当平台名称不支持时
        """
        platform_name = platform_name.lower()

        # 使用单例模式，避免重复创建实例
        if platform_name in cls._instances:
            return cls._instances[platform_name]

        if platform_name not in cls._providers:
            available_platforms = list(cls._providers.keys())
            raise ValueError(
                f"Unsupported platform: {platform_name}. "
                f"Available platforms: {available_platforms}"
            )

        provider_class = cls._providers[platform_name]
        instance = provider_class(platform_name)
        cls._instances[platform_name] = instance

        logger.info(f"Created platform provider instance: {platform_name}")
        return instance

    @classmethod
    def get_supported_platforms(cls) -> list[str]:
        """获取支持的平台列表

        Returns:
            支持的平台名称列表
        """
        return list(cls._providers.keys())

    @classmethod
    def is_supported(cls, platform_name: str) -> bool:
        """检查平台是否支持

        Args:
            platform_name: 平台名称

        Returns:
            是否支持该平台
        """
        return platform_name.lower() in cls._providers


def get_platform_provider(platform_name: str) -> PlatformProvider:
    """获取平台提供者实例的便捷函数

    Args:
        platform_name: 平台名称

    Returns:
        平台提供者实例
    """
    return PlatformFactory.create(platform_name)


def register_platform(platform_name: str):
    """平台注册装饰器

    用于自动注册平台提供者类。

    Args:
        platform_name: 平台名称

    Returns:
        装饰器函数
    """

    def decorator(provider_class: Type[PlatformProvider]):
        PlatformFactory.register(platform_name, provider_class)
        return provider_class

    return decorator
