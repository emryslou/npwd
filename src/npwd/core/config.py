from typing import Dict, Any
from pathlib import Path
from os import getcwd, environ, path as os_path

_config_default: Dict = {
    'runtime_path':  str(Path(os_path.expandvars('%AppData%')).joinpath('npwd')) if environ.get('NPWD_ENV', 'PROD').upper() == 'PROD' else getcwd(),
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
            'buy': '我想进行一笔快速交易，预期收益 >= 3%, 预期亏损 <= 1% 请结合图中表的数据，给我一个切实可行的买入操作建议，最好当天可以完成， 例如买入价位，卖出价位',
            'sell': '我现在已经持有一笔交易，买入价格为 96500, 预期收益 >= 1%, 预期亏损 <= 0.5%， 请结合图中表的数据，给我一个切实可行的买入操作建议，例如卖出价位',
        },
        'model': 'minicpm-v:latest'
    }
}

_config: Dict = _config_default.copy()


def init(**kwargs):
    """初始化 config
    Args:
        ...
    """
    if 'config' in kwargs and kwargs['config']:
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
            _version = str(_cfg['version']) if 'version' in _cfg and _cfg['version'] else '1'
            match _version:
                case '1':
                    _cfg = _cfg['config'] if 'config' in _cfg and isinstance(_cfg['config'], dict) else {}
                    if 'runtime_path' in _cfg:
                        del _cfg['runtime_path']
                    _config.update(**_cfg)
                case _:
                    print('Warning: {} not supported'.format(_version))

            # 防止 kwargs 的空参数意外覆盖 已经配置好的 key
            for key in _cfg.keys():
                if key in kwargs:
                    del kwargs[key]
        else:
            print('Warning: {} not exists'.format(_config_path))
    
    if kwargs:
        _config.update(**kwargs)


def _load_python_yaml(_path: str | Path) -> dict:
    """从 yaml 文件 加载配置
    Args:
        _path: str | Path  # Yaml 文件 路径
    """
    with open(_path, encoding='utf-8') as _cfg:
        import yaml
        _cfg = yaml.load(_cfg, Loader=yaml.Loader)
        return _cfg


def _load_python_json(_path: str | Path) -> dict:
    """从 json 文件 加载配置
    Args:
        _path: str | Path  # json 文件 路径
    """
    with open(_path, encoding='utf-8') as _cfg:
        import json
        _cfg = json.load(_cfg)
        return _cfg


def get(key: str, default=None) -> Any:
    """读取配置"""
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
    """设置配置
    Args:
        key: str  # 支持 some or foo.some
        value: Any  # 保存值
    """

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
    """读取所有配置"""
    return _config


def dumps(dump_format: str) -> str:
    """序列化配置
    Args:
        dump_format: str, one of 'json' or 'yaml' or 'yml'
    """
    _dump_data = {
        'version': '1',
        'config': all(),
    }
    del _dump_data['config']['runtime_path']
    match dump_format:
        case 'json':
            import json
            return json.dumps(_dump_data)
        case 'yml' | 'yaml':
            import yaml
            return yaml.dump(_dump_data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        case _:
            raise BaseException('Error: Unsupported Format {}'.format(dump_format))


def dump(file_path: str | Path, dump_format: str) -> None:
    """配置文件输出到指定文件
    Args:
        file_path: str | Path  # 要输出的文件
        dump_format: str, one of 'json', 'yml' or 'yaml' # 输出格式
    """
    _dump_data = {
        'version': '1',
        'config': all(),
    }
    del _dump_data['config']['runtime_path']
    match dump_format:
        case 'json':
            import json
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(_dump_data, fp=f)
        case 'yml' | 'yaml':
            import yaml
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(_dump_data, stream=f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        case _:
            raise BaseException('Error: Unsupported Format {}'.format(dump_format))


__import__ = ['init', 'get', 'all', 'set', 'dumps', 'dump']
