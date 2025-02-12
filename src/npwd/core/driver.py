from enum import Enum
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy, ProxyType
from typing import List
import sys

from . import config, tools


class DriverType(Enum):
    Edge = 1
    Chrome = 2
    Safari = 3

class PlatformType(Enum):
    UnknownPlatform = 0
    Windows = 1
    Linux = 2
    MacOS = 3

__platform_default_driver: dict = {
    str(PlatformType.Windows.name): str(DriverType.Edge.name),
    str(PlatformType.Linux.name): str(DriverType.Chrome.name),
    str(PlatformType.MacOS.name): str(DriverType.Safari.name),
}


def driver_type_names() -> List[str]:
    return DriverType.__dict__['_member_names_']

def driver_default_type() -> str:
    _plaform = platform()
    try:
        return __platform_default_driver[_plaform]
    except KeyError:
        return 'Unknown'

def platform():
    check_prefix = {
        'win': PlatformType.Windows.name,
        'linux': PlatformType.Linux.name,
        'darwin': PlatformType.MacOS.name,
    }
    for key, sys_type in check_prefix.items():
        if sys.platform.startswith(key):
            return sys_type
    
    return 'Unknown Platform'


def init_driver(driver_type: DriverType):

    match driver_type:
        case DriverType.Edge:
            driver = init_edge()
        case DriverType.Chrome:
            driver = init_chrome()
        case _:
            raise NotImplementedError()
    driver.set_page_load_timeout(int(config.get('timeout', 60)))
    driver.maximize_window()

    min_tab_count = int(config.get('tab-count', 2))
    while len(driver.window_handles) < min_tab_count:
        driver.execute_script('window.open("");')

    return driver


def init_edge_options():
    _options = webdriver.EdgeOptions()
    _options.add_argument('User-Agent={}'.format(UserAgent(os=platform()).random))  # 设置 UA
    _options.add_argument('log-level=3')  # 日志级别

    if config.get('headless', True):
        _options.add_argument('--headless')
    
    proxy_addr = str(config.get('proxy', ''))
    if len(proxy_addr):
        _proxy = Proxy()
        _proxy.proxy_type = ProxyType.MANUAL
        _proxy.http_proxy = proxy_addr
        _options.add_argument('--proxy-server=http://{}'.format(proxy_addr))
    return _options


def init_edge():
    options = init_edge_options()
    driver = webdriver.Edge(options=options)
    
    return driver


def init_chrome():
    """ 初始化一个 Chrome 浏览器对象 """
    def chrome_options():
        _options = webdriver.ChromeOptions()
        _options.add_argument('User-Agent={}'.format(UserAgent(os=platform()).random)) # 设置 UA
        _options.add_argument('log-level=3') # 日志级别
        if config.get('headless', True):
            _options.add_argument('--headless')
        
        proxy_addr = str(config.get('proxy', ''))
        if len(proxy_addr):
            _proxy = Proxy()
            _proxy.proxy_type = ProxyType.MANUAL
            _proxy.http_proxy = proxy_addr
            _options.add_argument('--proxy-server=http://{}'.format(proxy_addr))
        
        return _options

    driver = webdriver.Chrome(
        service=webdriver.ChromeService(
                executable_path=str(tools.bin_path().joinpath(config.get('driver.chrome.path')))
            ),
        options=chrome_options(),
    )

    return driver
