import threading, time, json
from fake_useragent import UserAgent
from loguru import logger
from typing import List, Optional, Tuple, Any, Callable
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
    progress_total, seconds_readable,
    ProgressMetaType as PMT,
    ProgressMetaFileStatus as PMFS,
    ProgressMetaLineStatus as PMLS,
)

__version__ = 'v3.2025.02.01'

def init_browser() -> webdriver.Chrome:
    """ 初始化一个 浏览器对象 """
    def chrome_options():
        from selenium.webdriver.chrome.options import Options
        _options = Options()
        _options.add_argument('User-Agent={}'.format(UserAgent(os='Windows').random)) # 设置 UA
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
    
    driver = webdriver.Chrome(service=webdriver.ChromeService(executable_path=chrome_bin('v132')), options=chrome_options())
    driver.set_page_load_timeout(int(config.get('timeout', 60)))
    driver.maximize_window()

    min_tab_count = int(config.get('tab-count', 2))
    while len(driver.window_handles) < min_tab_count:
        driver.execute_script('window.open("");')

    return driver

@handle_exception
def capture_worker(mq: ManageQueue, driver: webdriver.Chrome, url: UrlInfo, win: Optional[str] = None) -> Tuple[str, Optional[Path]]:
    """ 处理 url """
    finally_message = True
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
        
        # 转交给页面处理器，或抓去网页内容，或截取图片等等
        result = dispatch_handler(url, driver)
        logger.info('{} result: {}', url, result)
        if config.get('with_progress', False):
            send_progress_meta(
                mq,
                meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source, status=PMLS.Succeed,
                message = f'{url.source}:{url.src_idx}: result: {result}'
            )
            finally_message = False
        return (win, None)
    except BaseException as e:
        if isinstance(e, WebDriverException):
            logger.error("{} 访问失败, 错误信息: {}", url.url, str(e))
        if config.get('with_progress', False):
            send_progress_meta(
                mq,
                meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source, status=PMLS.Failure,
                message = f'{url.source}:{url.src_idx}: error: {str(e)}'
            )
            finally_message = False
        return (win, None)
    finally:
        if finally_message and config.get('with_progress', False):
            send_progress_msg(mq, message=f'{url.source} at Line {url.src_idx}: {url.url} 已完成')

@hook_log
def proc_url(mq: ManageQueue, driver: webdriver.Chrome):
    """ 从队列中读取行数据，并交付给 url 抓取方法处理 """
    win_tab_count = len(driver.window_handles)
    win_tab_idx = 0
    while mq.running():
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
            if not mq.running(): break
            logger.debug('任务 {}: 队列为空, 稍后重试', func_name())

def push_url_proc_queue(mq: ManageQueue, file: str):
    """ 逐行读取文件内容，判断行是否有效，然后排队待处理 """
    logger.info('任务 {}: 开始处理文件 {}', func_name(), file)
    with open(file, encoding='utf-8') as f:
        line_no = 0
        while mq.running():
            ctx = f.readline()
            line_no += 1
            if not ctx: break
            if config.get('with_progress', False):
                send_progress_meta(
                    mq,
                    meta_type=PMT.LINE, data=f'{file}:{line_no}', parent=str(file),
                    total=progress_total(data=f'{file}:{line_no}', meta_type=PMT.LINE),
                )
            if not ctx.strip() or len(ctx) <= 23 or ctx.startswith('#'):
                logger.warning('任务 {}: 文件 {} 第 {} 行内容 {} 可能不是有效数据， 跳过 ', func_name(), file, line_no, ctx)
                if config.get('with_progress', False):
                    send_progress_meta(
                        mq, meta_type=PMT.LINE, data='{file}:{line_no}', 
                        message=f'URL 源 {file} 第 {line_no} 行，不是有效数据，不做处理', parent=str(file), status=PMLS.Failure,
                    )
                continue
            try:
                url_info = dict(json.loads(ctx))
            except json.JSONDecodeError as jde:
                send_progress_meta(
                    mq, meta_type=PMT.LINE, data='{file}:{line_no}', 
                    message=f'URL 源 {file} 第 {line_no} 行，数据解析失败，跳过 {jde}', parent=str(file), status=PMLS.Failure,
                )
                continue
            
            idle_time = 5
            while mq.running():
                try:
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
def proc_file(mq: ManageQueue):
    """ 从队列中获取文件转交给文件处理器 """
    while mq.running():
        try:
            file = mq.get('file', timeout=5)
            try:
                if config.get('with_progress', False):
                    send_progress_meta(
                        mq, meta_type=PMT.FILE, data=str(file), status=PMFS.Processed,
                        message=f'开始处理 {file} 文件'
                    )
                push_url_proc_queue(mq, file)
            finally:
                mq.task_done('file')
        except Empty:
            if not mq.running(): break
            logger.debug('任务 {}: 队列为空，稍后再试', func_name())

@hook_log
def push_proc_file_queue(mq: ManageQueue, file: str) -> None:
    """ 待处理的文件排队 """
    idle_time = 10
    while mq.running():
        try:
            mq.put_nowait('file', file)
            if config.get('with_progress', False):
                send_progress_meta(
                    mq, meta_type=PMT.FILE, data=str(file), status=PMFS.Queued,
                )
            idle_time = 10
            break
        except Full:
            if not mq.running(): break
            logger.debug('任务 {}: 队列已满，稍后重试', func_name())
            time.sleep(idle_time)
            idle_time = min(100, idle_time * 1.2)

@hook_log
def path_monitor(mq: ManageQueue, path: str):
    """ 监控目录中是否有新文件创建 """
    def on_file_created(event: FileSystemEvent):
        logger.info('任务{}: 检测到 新文件 {} 被创建，稍后处理', func_name(), event.src_path)
        if config.get('with_progress', False):
            send_progress_meta(
                mq,
                meta_type=PMT.FILE, data=event.src_path,
                total=progress_total(data=event.src_path, meta_type=PMT.FILE),
                message=f'检测到 新文件 {event.src_path} 被创建，开始排队'
            )
        push_proc_file_queue(mq, event.src_path)

    obsrv = Observer()
    obsrv.schedule(event_handler=UrlSourceEventHandler(created=on_file_created), path=path, recursive=True)
    obsrv.start()
    try:
        while mq.running() and obsrv.is_alive():
            obsrv.join(1)
    finally:
        obsrv.stop()
        obsrv.join()

def show_progress(mq: ManageQueue):
    """ 显示任务处理情况 """
    from rich.progress import Progress
    tasks:dict = {}
    with Progress(transient=True) as progress:
        def update_task(key: str) -> None:
            progress.update(tasks[key]['task'], advance=1)
            tasks[key]['total'] -= 1
            if (tasks[key]['total'] <= 0):
                send_progress_msg(mq, f"{key} 已完成，关闭显示进度")
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
        
        while mq.running():
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


def idle_timeout_task(mq: ManageQueue):
    interval = config.get('idle_timeout', 600)
    def create_timer(delay: float, call: Callable, *args, **kwargs):
        t = threading.Timer(delay, function=call, args=args, kwargs=kwargs)
        t.start()

    def ticker_callback(delay: float, mq: ManageQueue):
        if mq.running() and mq.idle(float(interval)):
            mq.update_checkpoint('file')
            path = config.get('source', '')
            send_progress_msg(mq, message=f'定时任务: 发送 {path} 中的文件')
            send_files_from_path(mq, path)

        if mq.running():
            create_timer(delay, ticker_callback, delay, mq=mq)
    
    send_progress_msg(mq, '空闲超时任务启动: {} ....'.format(seconds_readable(interval)))
    ticker_callback(1, mq)

def send_files_from_path(mq: ManageQueue, path: str):
    # 处理已经存在文件
    for file in Path(path).iterdir():
        if config.get('with_progress', False):
            send_progress_meta(
                mq, meta_type=PMT.FILE, data=str(file),
                total=progress_total(data=str(file), meta_type=PMT.FILE),
                message=f'{path}中的文件 {file} 开始排队 ...'
            )
        push_proc_file_queue(mq, file)
    else:
        pass


def stop_and_wait_threads(mq: ManageQueue, threads: List[threading.Thread], timeout: int|None = None):
    """ 停止并等待所有线程结束 """
    mq.stop()
    [ _t.join(timeout) for _t in threads ]

def start(monitor_path: str | None = None):
    logger.info('欢迎使用，程序开始...')

    monitor_path = monitor_path if monitor_path else config.get('source', '')
    driver = init_browser()
    quit_timeout = config.get('timeout', 60) # 退出信号超时时间，秒
    with_progress = config.get('with_progress', False)
    mq_kwargs = { 'file': 2, 'url': 10, }
    if with_progress:
        mq_kwargs['progress'] = 300
    
    mq = ManageQueue(*tuple(mq_kwargs.keys()), **mq_kwargs)
    threads:List[threading.Thread] = [
        threading.Thread(name='ProcUrl', target=proc_url, args=(mq, driver)) # 处理 URL
    ]

    if with_progress:
        new_threads = [threading.Thread(name='Progress', target=show_progress, args=(mq,))]
        new_threads.extend(threads)
        threads[:] = new_threads[:]

    if Path(monitor_path).is_dir(): # 监控源 为目录时 启动 目录监控 和 目录下文件排队
        if config.get('idle_task', False):
            threads.append(threading.Thread(name='Ticker', target=idle_timeout_task, args=(mq,)),)
        if config.get('source_watch', False): # 监控目录
            threads.append(threading.Thread(name='PathMonitor', target=path_monitor, args=(mq, monitor_path,)))
        # 文件排队
        threads.append(threading.Thread(name='ProcFile', target=proc_file, args=(mq,)))


    [ _t.start() for _t in threads ]
    try:
        if Path(monitor_path).is_dir():
            # 处理已经存在文件
            send_files_from_path(mq, monitor_path)
            if config.get('source_watch', False):
                if with_progress:
                    send_progress_msg(mq, message=f'监控目录: {monitor_path}')
                while True: time.sleep(10)
            else:
                mq.join('file')
                mq.join('url')
        else:
            if with_progress:
                meta_list = [
                    {'total':progress_total(data=monitor_path, meta_type=PMT.FILE), 'message': f'处理文件: {monitor_path}'},
                    {'status': PMFS.Queued},
                    {'status': PMFS.Processed}
                ]
                for meta in meta_list:
                    send_progress_meta(
                        mq, meta_type=PMT.FILE, data=monitor_path, **meta
                    )
            push_url_proc_queue(mq, monitor_path)
            mq.join('url')
        send_progress_msg(mq, message=f'{monitor_path} 内容全部处理完成')
    except KeyboardInterrupt:
        logger.info('感谢使用，程序预计在 {} 秒内退出', quit_timeout)
        if with_progress:
            send_progress_msg(
                mq, message=f'感谢使用，程序预计在 {quit_timeout} 秒内退出'
            )
    finally:
        if with_progress:
            mq.join('progress')
        stop_and_wait_threads(mq, threads, quit_timeout)
        driver.quit()
