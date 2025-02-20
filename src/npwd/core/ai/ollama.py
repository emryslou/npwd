import httpcore
from typing import List, Union
from pathlib import Path
from ollama import Client

from .provider import Provider


class OllamaProvider(Provider):
    """ollama"""

    name = 'ollama'

    def __init__(self, host: str, model: str, **kwargs):
        self.host = host
        self.model = model
        self.config = kwargs
        self._client: Client = Client(host=self.host)

    def chat(self, images: List[Union[str, Path]] = [], _q: str | None = None) -> str:
        """和AI会话
        Args:
            images: List[Union[str, Path]]  # 图片列表
            _q: str | None  # 提问内容，可选 # 暂时用不到
        Return:
            str
        """
        try:
            content: str = self.config['prompts']['buy']
            if 'buy_map' in self.config['prompts'] and isinstance(self.config['prompts']['buy_map'], dict):
                content = content.format_map(self.config['prompts']['buy_map'])
            req_params = {
                'model': self.config.get('model', 'minicpm-v:latest'),
                'messages': [{
                    'role': 'user',
                    'content': content,
                    'images': images,
                }],
                'stream': True
            }
            res = self._client.chat(**req_params)
            advise = []
            print(f'Q: {content}', flush=True)
            print('A: ', end='')
            for message in res:
                print(message['message']['content'], end='')
                advise.append(message['message']['content'])
            return ''.join(advise)
        except (httpcore.TimeoutException, httpcore.ConnectTimeout, httpcore.ConnectError) as ce:
            print(f'Warning: AI Client Connect Error, more: {ce}')
            return ''
