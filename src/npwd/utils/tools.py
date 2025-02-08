from typing import Optional, Union, List, Callable, Any
from pathlib import Path
from functools import lru_cache
import sys, os
from loguru import logger
from enum import Enum, IntEnum

def func_name(depth: int = 1):
    return sys._getframe(depth).f_code.co_name

@lru_cache(maxsize=512)
def root_path(custom_root_path: str | None = None) -> Path:
    custom_root_path = custom_root_path if custom_root_path else os.getcwd()
    return Path(custom_root_path)

def data_path() -> Path:
    return root_path().joinpath('data')

def img_path() -> Path:
    return data_path().joinpath('img')

def txt_path() -> Path:
    return data_path().joinpath('txt')

def log_path() -> Path:
    return root_path().joinpath('log')

def save_path(name: str, file_path: Optional[str] = None, postfix: Optional[callable] = None, file_type: str = 'img') -> Path:
    if postfix:
        if not isinstance(postfix(), str):
            raise TypeError('the function postfix must returned a string')
        try:
            ext = name.split('.')[-1]
            file = '.'.join(name.split('.')[:-1])
            name = f'{file}{postfix()}.{ext}'
        except ValueError:
            name = f'{name}{postfix()}'

    _paths = [file_path, name] if file_path else [name]

    def save_root_path(file_type: str) -> Path:
        match file_type:
            case 'img':
                return img_path()
            case 'txt':
                return txt_path()
            case _:
                return data_path().joinpath(str(file_type))

    _save_path = save_root_path(file_type).joinpath(*_paths)
    if not _save_path.parent.exists():
        _save_path.parent.mkdir(parents=True)
    return _save_path

def backup_file(file_path: Union[Path, str]) -> Path:
    file_path = Path(file_path)
    try:
        [file, ext] = file_path.name.split('.', 2)
        ext = f'.{ext}'
    except ValueError:
        [file, ext] = [file_path.name, '']

    import time
    backup_at = time.strftime('%Y%m%d%H%M%S')
    new_file =  file_path.parent.joinpath(f'{file}.bak.{backup_at}{ext}')
    file_path.rename(new_file)
    return new_file

def bin_path(sub_path: Optional[str] = None) -> Path:
    return root_path().joinpath('bin').joinpath(sub_path) if sub_path else  root_path().joinpath('bin')

def chrome_bin(v: Optional[str] = None) -> Path:
    v = v if v else 'v133'
    return bin_path('chromedriver-win64').joinpath(v).joinpath('chromedriver.exe')

def load_handlers(handler_config: List[str]):
    import importlib

    for item in handler_config:
        item_path = Path(item)
        if not item_path.exists():
            logger.warning('{} [real path: ] cannot be found and will be skipped', item_path)
            continue
        if item_path.is_dir():
            if item_path.joinpath('__init__.py').exists():
                module_name = item.replace('/', '.').replace('\\', '.')
                # print(module_name)
                # print(f'{item_path} is a package')
                if str(item_path.parent) not in sys.path:
                    sys.path.append(str(item_path.parent))
                importlib.import_module(module_name.split('.')[-1], str(item_path))
            else:
                NotImplementedError('TODO: not a package ')
        elif item_path.is_file():
             NotImplementedError('TODO: a file import')
        else:
            pass

def platform():
    check_prefix = {
        'win': 'Windows',
        'linux': 'Linux',
        'darwin': 'MacOS'
    }
    for key, sys_type in check_prefix.items():
        if sys.platform.startswith(key):
            return sys_type
    
    return 'Unknown Platform'

def handle_exception(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BaseException as e:
            logger.error('任务 {}: 抛出异常信息，具体信息为: {}, 参数: args: {}, kwargs: {}', func.__name__, str(e), args, kwargs)
    
    return wrapper

def hook_log(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        logger.debug('任务 {}: 开始 ...', func.__name__)
        result = func(*args, **kwargs)
        logger.debug('任务 {}: 结束 -_-', func.__name__)
        return result
    
    return wrapper

def seconds_readable(seconds: int | float) -> str:
    units: dict = {
        '天': 86400, '小时': 3600,
        '分': 60, '秒': 1,
    }

    ret = ''
    for unit_name, unit_size in units.items():
        unit_real_size = int(seconds / unit_size)
        if unit_real_size > 0:
            ret = '{} {} {}'.format(ret, int(seconds / unit_size), unit_name)
            seconds = seconds % unit_size
    return ret


def remove_expired_files(expired: int, file_or_dir: Path):
    if not file_or_dir.exists():
        return
    
    import time
    now = time.time()
    for data_path in file_or_dir.iterdir():
        if data_path.is_dir():
            remove_expired_files(expired, data_path)
        elif data_path.is_file():
            if now - data_path.stat().st_ctime <= expired:
                continue
            data_path.unlink()
