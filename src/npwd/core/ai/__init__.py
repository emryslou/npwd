"""
AI 服务商
"""
from .ollama import OllamaProvider
from .provider import Provider, ProviderNotFound


def proxy_provider(provider_name: str, config: dict | None = None) -> Provider:
    """构建AI对象
    Args:
        provider_name: str  # AI 服务商: ollama
        config: dict | None  # 配置参数
    Return:
        Provider
    """
    for plugin in Provider.plugins:
        if provider_name == plugin.name:
            return plugin(**config)

    raise ProviderNotFound(f'Not Found {provider_name}')
