from ollama import Client
from pathlib import Path

# data/img/www.coinglass.com/block__zh_large-orderbook-statistics.比特币大额订单.20250211183416.png
img_path = Path(__file__).parent.parent.parent.parent.joinpath('data','img','www.coinglass.com', 'block__zh_large-orderbook-statistics.比特币大额订单.20250211183416.png')

c = Client(host='192.168.1.21:11434')

response = c.chat(
  model='minicpm-v:latest',
  messages=[
    {
      'role': 'user',
      'content': '请帮我分析一下图片内容，并对我后面的买入或者卖出提供可以实际操作的建议，谢谢; 如果没有有用的图表信息，则无需给出任何建议，谢谢啦',
      'images': [img_path],
    }
  ],
  stream=True
)

for m in response:
    print(m['message']['content'], end='', flush=True)
print()