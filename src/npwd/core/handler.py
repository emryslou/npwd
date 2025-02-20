from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Type, Any
from urllib3.util import parse_url
import time

from .tools import *
from .url_info import UrlInfo


def save_postfix():
    import time
    return '.{}'.format(time.strftime('%Y%m%d%H%M%S', time.localtime()))


class HandlerNotFound(Exception):
    pass


class Handler(object):
    name: Optional[str] = None

    plugins: List[Type["Handler"]] = []

    def __init__(self, *args: Any, **kwargs: Any):
        self.result = []  
    
    def __init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls.plugins.append(cls)
    
    def handler(self) -> Any:
        url_obj = parse_url(self.url.url)
        if hasattr(self.url, 'blocks'):
            def block_depends(depends: List | None = None):
                if not depends:
                    return
                for depend in depends:
                    _depend_ele = WebDriverWait(self.driver, config.get('timeout', 60)).until(
                        EC.visibility_of_element_located((depend["by"], depend["value"]))
                    )
                    for event in depend['events']:
                        if 'params' in event and event['params']:
                            getattr(_depend_ele, event['event'])(*event['params'])
                        else:
                            getattr(_depend_ele, event['event'])()
                    time.sleep(3)

            def snap_block(name: str, selector: str, depends: List | None = None):
                block_depends(depends)
                scf = WebDriverWait(self.driver, config.get('timeout', 60)).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                _file_name = '{}_{}.{}.{}'.format('block', url_obj.path.replace('/', '_') if url_obj.path else 'index', name, 'png')
                img_save_path_main = save_path(_file_name, url_obj.hostname or 'default', postfix=save_postfix)
                time.sleep(0.5)
                scf.screenshot(str(img_save_path_main))
                return img_save_path_main
            self.result.extend([{"name": block['name'], 'path': str(snap_block(**block))} for block in self.url.blocks])
        
        if hasattr(self.url, 'snap_full_page') and self.url.snap_full_page:
            file_name = '{}_{}.{}'.format(
                'page',
                url_obj.path.lstrip('/').replace('/', '_') if url_obj.path else 'index',
                'png'
            )
            img_save_path = save_path(file_name, url_obj.hostname or 'default', postfix=save_postfix)
            self.driver.save_screenshot(img_save_path)
            self.result.append({"name": self.url.name, "path": str(img_save_path)})


class Default(Handler):
    name = 'default'

    def __init__(self, url: UrlInfo, driver: webdriver.Chrome):
        self.url = url
        self.driver = driver
        super().__init__(url, driver)
