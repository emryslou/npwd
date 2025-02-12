from selenium import webdriver
from .url_info import UrlInfo, UrlSourceEventHandler, event_names
from .handler import Handler, Default, HandlerNotFound
from .manage_queue import ManageQueue
from .tools import *


def create_handler(url: UrlInfo, driver: webdriver.Chrome) -> Handler:
    for handler_class in Handler.plugins:
        if handler_class.name == url.handler:
            return handler_class(url, driver)
    raise HandlerNotFound()


def dispatch_handler(url: UrlInfo, driver: webdriver.Chrome) -> List:
    try:
        _handler = create_handler(url, driver)
    except HandlerNotFound:
        if url.handler != 'default':
            logger.warning('Url Handler [{}] cannot found, use [default]', url.handler)
        _handler = Default(url, driver)
    
    _handler.handler()
    return _handler.result


__all__ = [
    'UrlInfo', 'UrlSourceEventHandler',
    'config',
    'Handler', 'Default', 'HandlerNotFound', 'dispatch_handler',
    'ManageQueue',
    'root_path', 'save_path', 'data_path', 'bin_path', 'log_path', 'txt_path', 'img_path',
    'platform',
    'func_name',
    'load_handlers',
    'hook_log', 'handle_exception', 'seconds_readable', 'remove_expired_files',
]
