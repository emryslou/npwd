import threading, time, json
from loguru import logger
from typing import Callable, List, Optional, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent
from pathlib import Path
from queue import LifoQueue as Queue, Full, Empty
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.proxy import Proxy, ProxyType

from .core import UrlSourceEventHandler, UrlInfo, config, dispatch_handler
from .utils import func_name, chrome_bin, hook_log, handle_exception


def init_browser() -> webdriver.Chrome:
    def chrome_options():
        from selenium.webdriver.chrome.options import Options
        _options = Options()
        if config.get('headless', True):
            _options.add_argument('--headless')
        
        proxy_addr = str(config.get('proxy', ''))
        if len(proxy_addr):
            _proxy = Proxy()
            _proxy.proxy_type = ProxyType.MANUAL
            _proxy.http_proxy = proxy_addr
            _options.add_argument('--proxy-server=http://{}'.format(proxy_addr))
        
        return _options
    
    driver = webdriver.Chrome(service=webdriver.ChromeService(executable_path=chrome_bin('v132')), options=chrome_options())
    driver.set_page_load_timeout(int(config.get('timeout', 60)))
    driver.maximize_window()

    min_tab_count = int(config.get('tab-count', 2))
    while len(driver.window_handles) < min_tab_count:
        driver.execute_script('window.open("");')

    return driver

@handle_exception
def capture_worker(driver: webdriver.Chrome, url: UrlInfo, win: Optional[str] = None) -> Tuple[str, Optional[Path]]:
    try:
        if driver.current_window_handle != win:
            driver.switch_to.window(win)
        driver.get(url.url)

        if config.get('scroll_window_size', False):
            h = lambda x: driver.execute_script("return document.body.parentNode.scrollHeight")
            w = lambda x: driver.execute_script("return document.body.parentNode.scrollWidth")
            driver.set_window_size(w(0), h(0))
        
        while driver.current_window_handle != win:
            time.sleep(0.1)
            driver.switch_to.window(win)
        
        dispatch_handler(url, driver)
        return (win, None)
    except WebDriverException as wde:
        logger.warning(f"{url} accessed failed, error message: {wde}")
        return (win, None)

@hook_log
def proc_url(stop: threading.Event, url_proc_queue: Queue, driver: webdriver.Chrome):
    win_tab_count = len(driver.window_handles)
    win_tab_idx = 0
    while not stop.is_set():
        try:
            url_info = url_proc_queue.get(timeout=5)
            try:
                logger.info('任务 {}: 处理 {}', func_name(), url_info)
                capture_worker(driver, UrlInfo(**json.loads(url_info)), driver.window_handles[win_tab_idx])
                win_tab_idx = (win_tab_idx + 1) % win_tab_count
            finally:
                url_proc_queue.task_done()
        except Empty:
            if stop.is_set(): break
            logger.debug('任务 {}: 队列为空, 稍后重试', func_name())

@hook_log
def push_url_proc_queue(stop: threading.Event, url_proc_queue: Queue, file: str):
    logger.info('任务 {}: 开始处理文件 {}', func_name(), file)
    
    with open(file, encoding='utf-8') as f:
        line_no = 0
        while not stop.is_set():
            ctx = f.readline()
            line_no += 1
            if not ctx: break
            if not ctx.strip() or len(ctx) <= 23:
                logger.warning('任务 {}: 文件 {} 第 {} 行内容 {} 可能不是有效数据， 跳过 ', func_name(), file, line_no, ctx)
                continue
            idle_time = 5
            while not stop.is_set():
                try:
                    url_proc_queue.put_nowait(ctx)
                    idle_time = 5
                    break
                except Full:
                    time.sleep(idle_time)
                    idle_time *= 1.2
                    continue

@hook_log
def proc_file(stop: threading.Event, file_proc_queue: Queue, url_proc_queue: Queue):
    while not stop.is_set():
        try:
            file = file_proc_queue.get(timeout=5)
            try:
                push_url_proc_queue(stop, url_proc_queue, file)
            finally:
                file_proc_queue.task_done()
        except Empty:
            if stop.is_set(): break
            logger.debug('任务 {}: 队列为空，稍后再试', func_name())

@hook_log
def push_proc_file_queue(stop: threading.Event, file_proc_queue: Queue, file: str) -> None:
    retry_times = 20
    idle_time = 10
    while retry_times > 0:
        try:
            file_proc_queue.put_nowait(file)
            idle_time = 10
            break
        except Full:
            if stop.is_set(): break
            logger.debug('任务 {}: 队列已满，稍后重试', func_name())
            time.sleep(idle_time)
            idle_time = min(100, idle_time * 1.2) 
            retry_times -= 1
    
    if retry_times <= 0:
        logger.error('任务 {}: {} 排队失败', func_name(), file)

@hook_log
def path_monitor(stop: threading.Event, file_proc_queue: Queue, path: str):

    def on_file_created(event: FileSystemEvent):
        logger.info('任务{}: 检测到 新文件 {} 被创建，稍后处理', func_name(), event.src_path)
        push_proc_file_queue(stop, file_proc_queue, event.src_path)

    obsrv = Observer()
    obsrv.schedule(event_handler=UrlSourceEventHandler(created=on_file_created), path=path, recursive=True)
    obsrv.start()
    try:
        # 处理已经存在文件
        for file in Path(path).iterdir():
            if stop.is_set(): break
            push_proc_file_queue(stop, file_proc_queue, file)
        
        while not stop.is_set() and obsrv.is_alive():
            obsrv.join(1)
    finally:
        obsrv.stop()
        obsrv.join()

def stop_and_wait_threads(stop: threading.Event, threads: List[threading.Thread], timeout: int|None = None):
    """ 停止并等待所有线程结束 """
    stop.set()
    [ _t.join(timeout) for _t in threads ]

def start(monitor_path: str):
    logger.info('欢迎使用，程序开始...')

    driver = init_browser()
    quit_timeout = config.get('timeout', 60) # 退出信号超时时间，秒
    
    stop = threading.Event()
    file_proc_queue: Queue = Queue(maxsize=3)
    url_proc_queue: Queue = Queue(maxsize=30)
    threads:List[threading.Thread] = [
        threading.Thread(name='ProcUrl', target=proc_url, args=(stop, url_proc_queue, driver)) # 处理 URL
    ]

    if Path(monitor_path).is_dir(): # 监控源 为目录时 启动 目录监控 和 目录下文件排队
        threads.extend([
            threading.Thread(name='PathMonitor', target=path_monitor, args=(stop, file_proc_queue, monitor_path,)), # 监控目录
            threading.Thread(name='ProcFile', target=proc_file, args=(stop, file_proc_queue, url_proc_queue,)), # 文件排队
        ])


    [ _t.start() for _t in threads ]
    try:
        if Path(monitor_path).is_dir():
            while True: time.sleep(10)
        else:
            push_url_proc_queue(stop, url_proc_queue, monitor_path)
            url_proc_queue.join()
    except KeyboardInterrupt:
        logger.info('谢谢使用，程序预计在 {} 秒内退出', quit_timeout)
    finally:
        stop_and_wait_threads(stop, threads, quit_timeout)
        driver.quit()
        logger.info('程序结束，拜拜')
