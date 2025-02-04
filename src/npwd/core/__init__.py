from typing import List
from selenium import webdriver
from loguru import logger
from .url_info import UrlInfo, UrlSourceEventHandler, event_names
from .handler import Handler, Default, HandlerNotFound
from .manage_queue import ManageQueue

def create_handler(url: UrlInfo, driver: webdriver.Chrome) -> Handler:
    for handler_class in Handler.plugins:
        if handler_class.name == url.handler:
            return handler_class(url, driver)
    raise HandlerNotFound()

def dispatch_handler(url: UrlInfo, driver: webdriver.Chrome) -> List:
    try:
        handler = create_handler(url, driver)
    except HandlerNotFound:
        if url.handler != 'default':
            logger.warning('Url Handler [{}] cannot found, use [default]', url.handler)
        handler = Default(url, driver)
    
    handler.handler()
    return handler.result

__all__ = [
    'UrlInfo', 'UrlSourceEventHandler', 'event_names'
    'config',
    'Handler', 'Default', 'HandlerNotFound', 'dispatch_handler',
    'ManageQueue', # util v3
]