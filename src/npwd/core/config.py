from typing import Dict, Any

_config: Dict = {
    'url_handlers': {
        'vendor/url_handlers',
    },
    'level_log': 'INFO',
}

def init(**kwargs):
    _config.update(**kwargs)

def get(key: str, default=None) -> Any:
    return _config.get(key, default)

def all() -> Dict:
    return _config

__import__ = ['init', 'get', 'all']

if __name__ == '__main__':
    print(_config)
    init(a=1, b=[])
    print(_config)
    print(get('a'))
    print(get('c', []))
    print(all())