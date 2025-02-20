from selenium import webdriver
from npwd.core import UrlInfo, Handler, config
from npwd.core.ai import proxy_provider
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
            self.ai_analysis()

    def ai_analysis(self):
        if not self.ai_config or 'provider' not in self.ai_config:
            return ''

        provider_name = self.ai_config['provider']
        _config = self.ai_config.copy()
        del _config['provider']

        ai_client = proxy_provider(provider_name, _config)
        for (idx, result) in enumerate(self.result):
            self.result[idx]['ai_advise'] = ai_client.chat([result['path']])
