import threading, time, json
from fake_useragent import UserAgent
from loguru import logger
from typing import List, Optional, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent
from pathlib import Path
from queue import Full, Empty
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.proxy import Proxy, ProxyType


from .core import UrlSourceEventHandler, UrlInfo, config, dispatch_handler, ManageQueue
from .utils import (
    func_name, chrome_bin, hook_log, 
    handle_exception,
    send_progress_meta, send_progress_msg,
    progress_total,
    ProgressMetaType as PMT,
    ProgressMetaFileStatus as PMFS,
    ProgressMetaLineStatus as PMLS,
)


def init_browser() -> webdriver.Chrome:
    def chrome_options():
        from selenium.webdriver.chrome.options import Options
        _options = Options()
        _options.add_argument('User-Agent={}'.format(UserAgent(os='Windows').random))
        _options.add_argument('log-level=3')
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
def capture_worker(mq: ManageQueue, driver: webdriver.Chrome, url: UrlInfo, win: Optional[str] = None) -> Tuple[str, Optional[Path]]:
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
        
        result = dispatch_handler(url, driver)
        if config.get('with_progress', False):
            send_progress_meta(
                mq,
                meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source, status=PMLS.Succeed,
            )
        return (win, None)
    except BaseException as e:
        if isinstance(e, WebDriverException):
            logger.error("{} 访问失败, 错误信息: {}", url.url, e)
        if config.get('with_progress', False):
            send_progress_meta(
                mq,
                meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source, status=PMLS.Failure,
            )
        return (win, None)
    finally:
        if config.get('with_progress', False):
            send_progress_msg(mq, message=f'{url.source} at Line {url.src_idx}: {url.url} Completed')

@hook_log
def proc_url(stop: threading.Event, mq: ManageQueue, driver: webdriver.Chrome):
    win_tab_count = len(driver.window_handles)
    win_tab_idx = 0
    while not stop.is_set():
        try:
            url = UrlInfo(**json.loads(mq.get('url', timeout=5)))
            try:
                logger.info('任务 {}: 处理 {}', func_name(), url)
                if config.get('with_progress', False):
                    send_progress_meta(
                        mq,
                        meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source,
                        status=PMLS.Processed,
                    )
                capture_worker(mq, driver, url, driver.window_handles[win_tab_idx])
                win_tab_idx = (win_tab_idx + 1) % win_tab_count
            finally:
                mq.task_done('url')
        except Empty:
            if stop.is_set(): break
            logger.debug('任务 {}: 队列为空, 稍后重试', func_name())

def push_url_proc_queue(stop: threading.Event, mq: ManageQueue, file: str):
    logger.info('任务 {}: 开始处理文件 {}', func_name(), file)
    with open(file, encoding='utf-8') as f:
        line_no = 0
        while not stop.is_set():
            ctx = f.readline()
            line_no += 1
            if not ctx: break
            if config.get('with_progress', False):
                send_progress_meta(
                    mq,
                    meta_type=PMT.LINE, data=f'{file}:{line_no}', parent=str(file),
                    total=progress_total(data=f'{file}:{line_no}', meta_type=PMT.LINE),
                )
            if not ctx.strip() or len(ctx) <= 23:
                logger.warning('任务 {}: 文件 {} 第 {} 行内容 {} 可能不是有效数据， 跳过 ', func_name(), file, line_no, ctx)
                if config.get('with_progress', False):
                    send_progress_meta(
                        mq,
                        meta_type=PMT.LINE, data=f'{file}:{line_no}', parent=str(file), status=PMLS.Failure,
                    )
                continue
            idle_time = 5
            while not stop.is_set():
                try:
                    url_info = dict(json.loads(ctx))
                    url_info.update({'source': str(file), 'src_idx': line_no})
                    ctx = json.dumps(url_info)
                    mq.put_nowait('url', ctx)
                    if config.get('with_progress', False):
                        send_progress_meta(
                            mq,
                            meta_type=PMT.LINE, data=f'{file}:{line_no}', parent=str(file), status=PMLS.Queued,
                        )
                    idle_time = 5
                    break
                except Full:
                    time.sleep(idle_time)
                    idle_time *= 1.2
                    continue

@hook_log
def proc_file(stop: threading.Event, mq: ManageQueue):
    while not stop.is_set():
        try:
            file = mq.get('file', timeout=5)
            try:
                if config.get('with_progress', False):
                    send_progress_meta(
                        mq, meta_type=PMT.FILE, data=str(file), status=PMFS.Processed,
                    )
                push_url_proc_queue(stop, mq, file)
            finally:
                mq.task_done('file')
        except Empty:
            if stop.is_set(): break
            logger.debug('任务 {}: 队列为空，稍后再试', func_name())

@hook_log
def push_proc_file_queue(stop: threading.Event, mq: ManageQueue, file: str) -> None:
    idle_time = 10
    while not stop.is_set():
        try:
            mq.put_nowait('file', file)
            if config.get('with_progress', False):
                send_progress_meta(
                    mq, meta_type=PMT.FILE, data=str(file), status=PMFS.Queued,
                )
            idle_time = 10
            break
        except Full:
            if stop.is_set(): break
            logger.debug('任务 {}: 队列已满，稍后重试', func_name())
            time.sleep(idle_time)
            idle_time = min(100, idle_time * 1.2)

@hook_log
def path_monitor(stop: threading.Event, mq: ManageQueue, path: str):

    def on_file_created(event: FileSystemEvent):
        logger.info('任务{}: 检测到 新文件 {} 被创建，稍后处理', func_name(), event.src_path)
        if config.get('with_progress', False):
            send_progress_msg(
                mq, message=f'检测到 新文件 {event.src_path} 被创建，开始排队'
            )
            send_progress_meta(
                mq,
                meta_type=PMT.FILE, data=event.src_path,
                total=progress_total(data=event.src_path, meta_type=PMT.FILE),
            )
        push_proc_file_queue(stop, mq, event.src_path)

    obsrv = Observer()
    obsrv.schedule(event_handler=UrlSourceEventHandler(created=on_file_created), path=path, recursive=True)
    obsrv.start()
    try:
        # 处理已经存在文件
        for file in Path(path).iterdir():
            if stop.is_set(): break
            if config.get('with_progress', False):
                send_progress_msg(
                    mq, message=f'目录中已有有文件 {file} 开始排队 ...'
                )
                send_progress_meta(
                    mq,
                    meta_type=PMT.FILE, data=str(file),
                    total=progress_total(data=str(file), meta_type=PMT.FILE)
                )
            push_proc_file_queue(stop, mq, file)
        
        while not stop.is_set() and obsrv.is_alive():
            obsrv.join(1)
    finally:
        obsrv.stop()
        obsrv.join()

def show_proc_result(stop: threading.Event, mq: ManageQueue):
    from rich.progress import Progress
    tasks:dict = {}
    with Progress(transient=True) as progress:
        def update_task(key: str) -> None:
            progress.update(tasks[key]['task'], advance=1)
            tasks[key]['total'] -= 1
            if (tasks[key]['total'] <= 0):
                send_progress_msg(mq, f"{key} 已完成，不再显示进度")
                progress.remove_task(tasks[key]['task'])
                for (_, sub_task) in tasks[key]['sub_task'].items():
                    progress.remove_task(sub_task['task'])
                del tasks[key]
        
        def new_task(name: str, total: int | str, color: str):
            return {
                'task': progress.add_task(f'[{color}]{name}', total=total),
                'sub_task': {},
                'total': total,
            }
        
        while not stop.is_set():
            try:
                t = json.loads(mq.get('progress', timeout=1))
                match PMT(t['type']):
                    case PMT.FILE:
                        if t['data'] not in tasks.keys():
                            tasks[t['data']] = new_task(name=t['data'], total=t['total'], color='blue')
                        else:
                            update_task(t['data'])
                    case PMT.LINE:
                        if t['data'] not in tasks[t['parent']]['sub_task'].keys():
                            tasks[t['parent']]['sub_task'][t['data']] = new_task(name=t['data'], total=t['total'], color='green')
                        else:
                            progress.update(tasks[t['parent']]['sub_task'][t['data']]['task'], advance=1)
                            tasks[t['parent']]['sub_task'][t['data']]['total'] -= 1
                            update_task(t['parent'])
                    case PMT.INFO:
                        progress.console.log(f'Info: {t["message"]}')
                    case _:
                        progress.console.log(f'Unknown: {t["type"]} {t}')
                mq.task_done('progress')
            except Empty:
                continue


def stop_and_wait_threads(stop: threading.Event, threads: List[threading.Thread], timeout: int|None = None):
    """ 停止并等待所有线程结束 """
    stop.set()
    [ _t.join(timeout) for _t in threads ]

def start(monitor_path: str):
    logger.info('欢迎使用，程序开始...')

    driver = init_browser()
    quit_timeout = config.get('timeout', 60) # 退出信号超时时间，秒
    with_progress = config.get('with_progress', False)
    mq_kwargs = { 'file': 2, 'url': 10, }
    if with_progress:
        mq_kwargs['progress'] = 300
    
    stop = threading.Event()
    mq = ManageQueue(*tuple(mq_kwargs.keys()), **mq_kwargs)
    threads:List[threading.Thread] = [
        threading.Thread(name='ProcUrl', target=proc_url, args=(stop, mq, driver)) # 处理 URL
    ]

    if with_progress:
        new_threads = [threading.Thread(name='Progress', target=show_proc_result, args=(stop, mq,))]
        new_threads.extend(threads)
        threads[:] = new_threads[:]

    if Path(monitor_path).is_dir(): # 监控源 为目录时 启动 目录监控 和 目录下文件排队
        threads.extend([
            threading.Thread(name='PathMonitor', target=path_monitor, args=(stop, mq, monitor_path,)), # 监控目录
            threading.Thread(name='ProcFile', target=proc_file, args=(stop, mq,)), # 文件排队
        ])


    [ _t.start() for _t in threads ]
    try:
        if Path(monitor_path).is_dir():
            if with_progress:
                send_progress_msg(
                    mq, message=f'监控目录: {monitor_path}'
                )
            while True: time.sleep(10)
        else:
            if with_progress:
                send_progress_msg(
                    mq, message=f'处理文件: {monitor_path}'
                )
                send_progress_meta(
                    mq, meta_type=PMT.FILE, data=monitor_path,
                    total=progress_total(data=monitor_path, meta_type=PMT.FILE)
                )
                for status in [PMFS.Queued, PMFS.Processed]:
                    send_progress_meta(
                        mq, meta_type=PMT.FILE, data=monitor_path, status=status,
                    )
            push_url_proc_queue(stop, mq, monitor_path)
            mq.join('url')
    except KeyboardInterrupt:
        logger.info('感谢使用，程序预计在 {} 秒内退出', quit_timeout)
        if with_progress:
            send_progress_msg(
                mq, message=f'感谢使用，程序预计在 {quit_timeout} 秒内退出'
            )
    finally:
        stop_and_wait_threads(stop, threads, quit_timeout)
        driver.quit()
