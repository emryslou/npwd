from typing import Dict, Any
from pathlib import Path
from os import getcwd, environ

"""

@click.option('--config-path', type=click.Path(exists=True, file_okay=True), help='配置文件路径')
@click.option('--driver-type', type=click.Choice(driver.driver_type_names()), default=driver.driver_default_type(), help=f'浏览器驱动类型, 默认:{driver.driver_default_type()}')
@click.option('--source', type=click.Path(exists=True), default=None, help='需要处理文件或者目录', required=True)
@click.option('--source-watch', is_flag=True, type=click.BOOL, default=False, help='如果 source 目录，是否需要持续监控， 默认: True')
@click.option('--headless', is_flag=True, type=click.BOOL, default=True, help='是否开启无头浏览器，默认开启: True')
@click.option('--proxy', type=click.STRING, default='', help='代理地址, 格式: {ip or host}:{port}, 例如： 127.0.0.1:8080, proxy.host.com:9900')
@click.option('--timeout', type=click.IntRange(1, 3600), default=60, help='超时时间, 单位: 秒, 默认: 60')
@click.option('--tab-count', type=click.IntRange(1, 15), default=2, help='默认打开 标签页个数, 默认: 2')
@click.option('--scroll-window-size', is_flag=True, type=click.BOOL, default=False, help='是否滚动窗口, 默认: False')
@click.option('--with-progress', is_flag=True, type=click.BOOL, default=False, help='是否显示进度, 默认: False')
@click.option('--idle-task', is_flag=True, type=click.BOOL, default=False, help='是否启动空闲超时任务, 仅在 source 为目录时有效')
@click.option('--idle-timeout', type=click.IntRange(10, 86400), default=600, help='队列空闲超过多少秒后启动，默认: 600')
@click.option('--log-level', type=click.Choice(['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False), default='INFO', help='日志显示级别, 默认: INFO')
"""
_config_default: Dict = {
    'runtime_path':  str(Path().home()) if environ.get('NPWD_ENV', 'PROD').upper() == 'PROD' else getcwd(),
    'driver_type': 'Chrome',
    'source': 'src',
    'source_watch': False,
    'headless': True,
    'proxy': '',
    'timeout': 60,
    'tab_count': 2,
    'scroll_window_size': False,
    'with_progress': False,
    'idle_task': False,
    'idle_timeout': 600,
    'url_handlers': [
        'vendor/url_handlers',
    ],
    'level_log': 'INFO',
    'driver': {
        'chrome': {
            'path': str(Path('chromedriver-win64').joinpath('v132').joinpath('chromedriver.exe')),
        }
    },
    'ai': {
        'provider': 'ollama',
        'host': '192.168.1.21:11434',
        'prompts': {
            'buy': '我想进行一笔快速交易，预期收益 >= 1%, 预期亏损 <= 0.5% 请结合图中表的数据，给我一个切实可行的买入操作建议，最好当天可以完成， 例如买入价位，卖出价位',
            'sell': '我现在已经持有一笔交易，买入价格为 96500, 预期收益 >= 1%, 预期亏损 <= 0.5%， 请结合图中表的数据，给我一个切实可行的买入操作建议，例如卖出价位',
        },
        'model': 'minicpm-v:latest'
    }
}

_config: Dict = _config_default.copy()

def init(**kwargs):
    if 'config' in kwargs:
        _cfg = {}
        _config_path = Path(kwargs['config'])
        if _config_path.exists():
            match _config_path.suffix[1:]:
                case 'yaml' | 'yml':
                    _cfg = _load_python_yaml(Path(_config_path))
                case 'json':
                    _cfg = _load_python_json(Path(_config_path))
                case _:
                    print('Unsupported {}'.format(kwargs['config']))
            del kwargs['config']
            if 'runtime_path' in _cfg:
                del _cfg['runtime_path']
            _config.update(**_cfg)

            # 防止 kwargs 的空参数意外覆盖 已经配置好的 key
            for key in _cfg.keys():
                if key in kwargs:
                    del kwargs[key]
        else:
            print('Warning: {} not exists'.format(_config_path))
    
    if kwargs:
        _config.update(**kwargs)

def _load_python_yaml(_path: str | Path) -> dict:
    with open(_path, encoding='utf-8') as _cfg:
        import yaml
        _cfg = yaml.load(_cfg, Loader=yaml.Loader)
        _cfg = _cfg['config']
        return _cfg

def _load_python_json(_path: str | Path) -> dict:
    with open(_path, encoding='utf-8') as _cfg:
        import json
        _cfg = json.load(_cfg)
        _cfg = _cfg['config']
        return _cfg


def get(key: str, default=None) -> Any:

    result = _config.get(key, default)
    if not result:
        keys = key.split('.')
        keys.reverse()
        result = _config.get(keys.pop())
        while isinstance(result, dict) and keys:
            result = result.get(keys.pop())

        return result if not keys else default
    else:
        return result

def set(key: str, value: Any):
    if key in _config:
        _config[key] = value
    elif key.count('.'):
        keys = key.split('.')        
        cur_pos = 1
        p_key, sub_keys = '.'.join(keys[:cur_pos]), keys[cur_pos:]
        
        def __make_sub_config(_keys: list, _value: Any) -> dict:
            return {_keys[0]: _value if len(_keys) == 1 else __make_sub_config(_keys[1:], _value)}
        
        _config[p_key] = __make_sub_config(sub_keys, value)
    else:
       _config[key] = value

def all() -> Dict:
    return _config


__import__ = ['init', 'get', 'all', 'set']
