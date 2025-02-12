from typing import Dict, Any
from pathlib import Path
from os import getcwd

_config: Dict = {
    'url_handlers': [
        'vendor/url_handlers',
    ],
    'level_log': 'INFO',
    'driver': {
        'chrome': {
            'path': str(Path('chromedriver-win64').joinpath('v132').joinpath('chromedriver.exe')),
        }
    },
    'runtime_path': getcwd(),
    'driver_type': 'Chrome',
}


def init(**kwargs):
    _config.update(**kwargs)


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


def all() -> Dict:
    return _config


__import__ = ['init', 'get', 'all']
