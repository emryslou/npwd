from selenium import webdriver
from npwd.core import UrlInfo, Handler, config
from pathlib import Path


class CoinGlass(Handler):
    name = 'coin_glass'

    def __init__(self, url: UrlInfo, driver: webdriver.Chrome):
        self.url = url
        self.driver = driver
        self.ai_config = config.get('ai', {})
        super().__init__(url, driver)
    
    def handler(self):
        super().handler()
        if self.ai_config:
            self.ai_anlysis()

    def ai_anlysis(self):
        for (idx, result) in  enumerate(self.result):
            self.result[idx]['ai_advise'] = self.do_analysis(result['path'])
    
    def do_analysis(self, img_path: Path) -> str:
        if not self.ai_config or 'provider' not in self.ai_config:
            return ''
        match self.ai_config['provider']:
            case 'ollama':
                from ollama import Client
                if not self.ai_config or 'host' not in self.ai_config:
                    return ''
                self.ai_client = Client(host=self.ai_config['host'])
                content: str = self.ai_config['prompts']['buy']
                if 'buy_map' in self.ai_config['prompts']:
                    content = content.format_map(self.ai_config['prompts']['buy_map'])
                req_params = {
                    'model':self.ai_config.get('model', 'minicpm-v:latest'),
                    'messages': [
                        {
                        'role': 'user',
                        'content': content,
                        'images': [img_path],
                        }
                    ],
                    'stream': True
                }
                res = self.ai_client.chat(**req_params)
                advise = []
                print(f'Q: {content}')
                print('A: ', end='')
                for message in res:
                    print(message['message']['content'], end='')
                    advise.append(message['message']['content'])
                return ''.join(advise)
            case _:
                print('unsupported')
                return ''
