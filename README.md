# npwd
网页看门狗

# path
```
bin # 浏览器驱动执行文件目录
src # 源码路径
vendor # 自定义网页处理器
```

# config 文件说明
1. 支持文件类型：yml ｜ yaml ｜ json
2. Yml 文件示例:
```yml
# yml 文件
version: 1 # 版本 固定写法
config: # 版本，固定写法
  url_handlers: # 自定义的 URL 处理器，可配置多个
    - vendor/url_handlers
  level_log: INFO # 日志等级
  driver_type: Edge # 浏览器驱动类型: Edge, Chrome, Firefox
  ai: # AI 配置，目前仅支持 ollama
    provider: ollama # 支持厂商
    host: 192.168.1.21:11434 # 连接主机: 主机+端口
    prompts: # 提示词
      buy: 我想进行一笔快速交易，预期收益 >= {ev}, 预期亏损 <= {el} 请结合图中表的数据，给我一个切实可行的买入操作建议，最好当天可以完成， 例如买入价位，卖出价位 # 买入
      buy_map: # 替换 buy 关键词
        ev: 2%
        el: 1%
      sell: 我现在已经持有一笔交易，买入价格为 {buy_price}, 预期收益 >= {ev}, 预期亏损 <= {el}， 请结合图中表的数据，给我一个切实可行的买入操作建议，例如卖出价位 # 卖出
      sell_map: # 替换 sell 关键词
        buy_price: 96000
        ev: 2%
        el: 1%
    model: minicpm-v:latest # 模型
  source: demo  # URL 扫描目录 或者 文件路径
  source_watch: true # 是否监控 source， 当 source 为目录时有效
  idle_task: true # 是否启动空闲任务
  idle_timeout: 900 # 当系统空闲时间超过 多少 秒 后启动任务
  tab_count: 2 # 默认 tab 梳理
  scroll_window_size: false # 是否最大化窗口
  timeout: 60 # 浏览器驱动超时时间
  with_progress: true # 是否显示进程
  proxy: '' # 代理，格式：IP/HOST:PORT
```

# 3. 网页内容配置说明
- 文件格式为
```
# 每行为一个完整的 JSON 格式数据
{ ... }
{ ... }
```
- 每行JSON包含字段说明
```json5
{
    "name": "说明性文字", // 必填
    "url": "网页URL地址", // 必填
    "blocks": [ // 必填 ，可为空数组
        {
            "name": "btc", // 名称
            "selector": "css 选择器", // 元素选择器
            "depends": [ // 可选，依赖元素
                {
                    "by": "id", // 对应 from selenium.webdriver.common.by import By
                    "value": "...", // 元素选择器
                    "events": [ // 元素需要触发的事件
                        {
                            "event": "....", // 事件方法
                            "params": [ // 事件参数
                                "param_1",
                                "param_2",
                                ...
                                "param_xxx"
                            ]
                        }
                    ]
                }
            ]
        }
    ],
    "handler": "..." // 可选， 自定义处理器
}
```

# 关于changelog 说明
