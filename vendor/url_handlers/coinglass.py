from selenium import webdriver
from npwd.core import UrlInfo, Handler
from pathlib import Path
from ollama import Client


class CoinGlass(Handler):
    name = 'coin_glass'

    def __init__(self, url: UrlInfo, driver: webdriver.Chrome):
        self.url = url
        self.driver = driver
        self.ai_client = Client(host='192.168.1.21:11434')
        super().__init__(url, driver)
    
    def handler(self):
        super().handler()
        self.ai_anlysis()

    def ai_anlysis(self):
        for (idx, result) in  enumerate(self.result):
            self.result[idx]['ai_advise'] = self.do_ai_analysis(result['path'])
    
    def do_ai_analysis(self, img_path: Path) -> str:
        res = self.ai_client.chat(
            model='minicpm-v:latest',
            messages=[
                {
                'role': 'user',
                # 'content': '请帮我分析一下图片内容，并对我后面的买入或者卖出提供可以实际操作的建议，谢谢; 如果没有看到有用的图表信息，就直接告诉说无法给出合理建议',
                # 'content': '我现在想卖入一笔交易，预期收益 >= 2%, 预期亏损 <= 1%, 请结合图中表的数据，给我一个切实可行的买入操作建议， 例如买入价位，卖出价位，预计持仓多久时间',
                'content': '我想进行一笔快速交易，预期收益 >= 1%, 预期亏损 <= 0.5% 请结合图中表的数据，给我一个切实可行的买入操作建议，最好当天可以完成， 例如买入价位，卖出价位，是否可以达成预期',
                'images': [img_path],
                }
            ],
            stream=True
        )
        advise = ''
        print('AI 说:')
        for message in res:
            print('\t', message['message']['content'].strip(), end='', flush=True)
            advise = f"{advise}{message['message']['content']}"
        return advise
