import threading, time, json
from fake_useragent import UserAgent
from loguru import logger
from typing import List, Optional, Tuple, Any, Callable, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEvent
from pathlib import Path
from queue import Full, Empty
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.proxy import Proxy, ProxyType


from .core import UrlSourceEventHandler, UrlInfo, config, dispatch_handler, ManageQueue
from .utils import (
    func_name, chrome_bin, hook_log, platform,
    handle_exception,
    send_progress_meta, send_progress_msg,
    progress_total, seconds_readable, txt_path, data_path, remove_expired_files,
    ProgressMetaType as PMT,
    ProgressMetaFileStatus as PMFS,
    ProgressMetaLineStatus as PMLS,
    TaskManage,
)

__version__ = 'v0.0.4.2025.02.05'

def init_browser() -> webdriver.Chrome:
    """ 初始化一个 浏览器对象 """
    def chrome_options():
        from selenium.webdriver.chrome.options import Options
        _options = Options()
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
        send_progress_meta(
            mq,
            meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source, status=PMLS.Succeed,
            result=result, batch_id=url.batch_id
        )
        finally_message = False
        return (win, None)
    except BaseException as e:
        if isinstance(e, WebDriverException):
            logger.error("{} 访问失败, 错误信息: {}", url.url, str(e))
        send_progress_meta(
            mq,
            meta_type=PMT.LINE, data=f'{url.source}:{url.src_idx}', parent=url.source, status=PMLS.Failure,
            message = f'{url.source}:{url.src_idx}: error: {str(e)}', batch_id=url.batch_id,
        )
        finally_message = False
        return (win, None)
    finally:
        if finally_message:
            send_progress_msg(mq, message=f'{url.source} at Line {url.src_idx}: {url.url} 已完成')

@hook_log
def proc_url(mq: ManageQueue, driver: webdriver.Chrome):
    """ 从队列中读取行数据，并交付给 url 抓取方法处理 """
    win_tab_count = len(driver.window_handles)
    win_tab_idx = 0
    while mq.running():
        try:
            url = UrlInfo(**mq.get('url', timeout=5))
            try:
                logger.info('任务 {}: 处理 {}', func_name(), url)
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

def push_url_proc_queue(mq: ManageQueue, file: str, batch_id: str | None = None):
    """ 逐行读取文件内容，判断行是否有效，然后排队待处理 """
    logger.info('任务 {}: 开始处理文件 {}', func_name(), file)
    with open(file, encoding='utf-8') as f:
        line_no = 0
        while mq.running():
            ctx = f.readline()
            line_no += 1
            if not ctx: break
            send_progress_meta(
                mq, meta_type=PMT.LINE, data=f'{file}:{line_no}', parent=str(file),
                total=progress_total(data=f'{file}:{line_no}', meta_type=PMT.LINE),
                batch_id=batch_id,
            )
            if not ctx.strip() or len(ctx) <= 23 or ctx.startswith('#'):
                logger.warning('任务 {}: 文件 {} 第 {} 行内容 {} 可能不是有效数据， 跳过 ', func_name(), file, line_no, ctx)
                send_progress_meta(
                    mq, meta_type=PMT.LINE, data='{file}:{line_no}', 
                    message=f'URL 源 {file} 第 {line_no} 行，不是有效数据，不做处理', parent=str(file), status=PMLS.Failure,
                    batch_id=batch_id,
                )
                continue
            try:
                url_info = dict(json.loads(ctx))
            except json.JSONDecodeError as jde:
                send_progress_meta(
                    mq, meta_type=PMT.LINE, data='{file}:{line_no}', 
                    message=f'URL 源 {file} 第 {line_no} 行，数据解析失败，跳过 {jde}', parent=str(file), status=PMLS.Failure,
                    batch_id=batch_id,
                )
                continue
            
            idle_time = 5
            while mq.running():
                try:
                    url_info.update({'source': str(file), 'src_idx': line_no, 'batch_id': batch_id})
                    mq.put_nowait('url', url_info)
                    send_progress_meta(mq,
                        meta_type=PMT.LINE, data=f'{file}:{line_no}', parent=str(file), status=PMLS.Queued,
                    )
                    idle_time = 5
                    break
                except Full:
                    if not mq.running(): break
                    time.sleep(idle_time)
                    idle_time *= 1.2
                    continue

@hook_log
def proc_file(mq: ManageQueue):
    """ 从队列中获取文件转交给文件处理器 """
    while mq.running():
        try:
            data = mq.get('file', timeout=5)
            file, batch_id = data['file'], data['batch_id']
            try:
                send_progress_meta(
                    mq, meta_type=PMT.FILE, data=str(file), status=PMFS.Processed, message=f'开始处理 {file} 文件',
                )
                push_url_proc_queue(mq, file, batch_id)
            finally:
                mq.task_done('file')
        except Empty:
            if not mq.running(): break
            logger.debug('任务 {}: 队列为空，稍后再试', func_name())

@hook_log
def push_proc_file_queue(mq: ManageQueue, file: str, batch_id: str | None = None) -> None:
    """ 待处理的文件排队 """
    idle_time = 10
    while mq.running():
        try:
            mq.put_nowait('file', {'file': str(file), 'batch_id': batch_id})
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
    _now = time.time()
    def on_file_created(event: FileSystemEvent):
        logger.info('任务{}: 检测到 新文件 {} 被创建，稍后处理', func_name(), event.src_path)
        batch_id = mq.uuid(time.time() - _now >= 2)
        send_progress_meta(
            mq,
            meta_type=PMT.FILE, data=event.src_path,
            total=progress_total(data=event.src_path, meta_type=PMT.FILE),
            message=f'检测到 新文件 {event.src_path} 被创建，开始排队',
        )
        push_proc_file_queue(mq, event.src_path, batch_id)

    obsrv = Observer()
    obsrv.schedule(event_handler=UrlSourceEventHandler(created=on_file_created), path=path, recursive=True)
    obsrv.start()
    try:
        while mq.running() and obsrv.is_alive():
            obsrv.join(1)
    finally:
        obsrv.stop()
        obsrv.join()

def system_toast(file_path: str | Path):
    import os
    sys_type = platform()
    match sys_type:
        case 'Windows':
            from windows_toasts import Toast, WindowsToaster, ToastDuration
            toaster = WindowsToaster('Python')
            newToast = Toast()
            newToast.text_fields = ['注意啦', f'结果保存在 {file_path.name}，点击弹窗，可查看结果']
            newToast.on_activated = lambda _: os.startfile(file_path)
            newToast.duration = ToastDuration.Long
            toaster.show_toast(newToast)
        case _:
            print(f'暂不支持 {sys_type} ')


def clear_data_expired(mq: ManageQueue, data: str | Path):
    data = data if isinstance(data, Path) else Path(data)
    expired = int(config.get('data_expire_seconds', 86400))
    remove_expired_files(expired, data)


def show_progress(mq: ManageQueue):
    """ 显示任务处理情况 """
    from rich.progress import Progress
    with Progress(transient=True) as progress:
        tm = TaskManage(progress, mq)

        def hanle_results(* _, **kwargs):
            import markdown2 as markdown
            results = kwargs.get('results', None)
            if not results:
                return
            
            try:
                md_lines = ["# 数据汇总\n"]
                for r in results:
                    md_lines.append(f'## {r["name"]} \n ![{r["name"]}](file:///{r["path"]} "--")')
                md_text = '\n'.join(md_lines)
                
                save_file = 'html_{}.html'.format(time.strftime('%Y%m%d%H%M%S'))
                file_path = txt_path().joinpath(save_file)

                if not file_path.parent.exists():
                    file_path.parent.mkdir(parents=True)
                
                html = markdown.markdown(text=md_text)
                with open(file_path, mode='w') as f:
                    f.write(html)
                
                system_toast(file_path)
                if not mq.running():
                    print('Info: Result: {}'.format(save_file))
                else:
                    send_progress_msg(mq, message=f'Result save to {save_file}')
            except BaseException as be:
                print(f'error: {be}, results: {results}')
            

        def idle_callback(*args, **kwargs):
            def idle_timeout(*_args, **_kwargs):
                mq.update_checkpoint('file')
                path = config.get('source', '')
                send_progress_msg(mq, message=f'定时任务: 发送 {path} 中的文件')
                send_files_from_path(mq, path, batch_id=kwargs['batch_id'])
            
            hanle_results(*args, **kwargs)
            idle_timeout(*args, **kwargs)
        
        results = []
        batch_status: Dict[str, Dict[str, List[Any]]] = {}
        t: Dict | None = None
        while mq.running():
            try:
                t = mq.get('progress', timeout=1)
                try:
                    batch_id = t['batch_id']
                    match PMT(t['type']):
                        case PMT.FILE | PMT.LINE:
                            if not tm.find(t['data']):
                                color = 'blue' if PMT(t['type']) == PMT.FILE else 'green'
                                tm.create(key=t['data'], total=t['total'], color=color, parent=t['parent'])
                                if batch_id and t['parent']:
                                    if batch_id not in batch_status.keys():
                                        batch_status[batch_id] = {
                                            'task_keys': [t['data']],
                                            'results': []
                                        }
                                    else:
                                        batch_status[batch_id]['task_keys'].append(t['data'])
                            else:
                                def on_done(task_key):
                                    send_progress_msg(mq, f"{task_key} 已完成，关闭显示进度")
                                    if batch_id not in batch_status:
                                        return
                                    if task_key not in batch_status[batch_id]['task_keys']:
                                        return
                                    batch_status[batch_id]['task_keys'].remove(task_key)
                                    if 'result' in t.keys() and t['result']:
                                        if isinstance(t['result'], List):
                                            batch_status[batch_id]['results'].extend(t['result'])
                                        else:
                                            batch_status[batch_id]['results'].append(t['result'])
                                        del t['result']
                                    
                                    if len(batch_status[batch_id]['task_keys']) == 0:
                                        send_progress_meta(mq, meta_type=PMT.BATCH_DONE, batch_id=batch_id)
                                
                                def on_err(err, trace, params):
                                    _key, _tasks = params['task_key'], params['tasks'] 
                                    send_progress_msg(mq, f'TaskManage Error: {err}, more: {trace}, \nParams: key: {_key}, all_tasks: {_tasks}')
                                
                                tm.update(t['data'], on_done=on_done, on_err=on_err)
                        case PMT.INFO:
                            progress.console.log(f'Info: {t["message"]}')
                        case PMT.IDLE:
                            data = results[:]
                            results.clear()
                            idle_callback(results=data, batch_id=batch_id)
                        case PMT.BATCH_DONE:
                            hanle_results(results=batch_status[batch_id]['results'])
                            del batch_status[batch_id]
                        case _:
                            progress.console.log(f'Unknown: {t["type"]} {t}')
                    
                    task_results = t.get('result', None)
                    if task_results:
                        if isinstance(task_results, List):
                            results.extend(task_results)
                        else:
                            results.append(task_results)
                except BaseException as e:
                    progress.console.log(f'Progress Error: {e}')
                    mq.stop()
                    raise e
                finally:                
                    mq.task_done('progress')
            except Empty:
                continue
        
        hanle_results(results=results)


def idle_timeout_ticker(mq: ManageQueue):
    """ 超时任务处理 """
    interval = config.get('idle_timeout', 600)
    def create_timer(delay: float, call: Callable, *args, **kwargs):
        t = threading.Timer(delay, function=call, args=args, kwargs=kwargs)
        t.start()

    def ticker_callback(delay: float, mq: ManageQueue):
        if mq.running() and mq.idle(10):
            clear_data_expired(mq, data=data_path())
        
        if mq.running() and config.get('idle_task', False) and mq.idle(float(interval)):
            # send_files_from_path(mq, path=config.get('source'), batch_id=mq.uuid(True))
            send_progress_meta(mq, meta_type=PMT.IDLE, batch_id=mq.uuid(True))
        
        if mq.running():
            create_timer(delay, ticker_callback, delay, mq=mq)
    
    if config.get('source_watch', False):
        send_progress_msg(mq, '空闲超时任务启动: {} ....'.format(seconds_readable(interval)))
    ticker_callback(1, mq)

def send_files_from_path(mq: ManageQueue, path: str, batch_id: str | None = None):
    # 处理已经存在文件
    for file in Path(path).iterdir():
        send_progress_meta(
            mq, meta_type=PMT.FILE, data=str(file),
            total=progress_total(data=str(file), meta_type=PMT.FILE),
            message=f'{path}中的文件 {file} 开始排队 ...',
        )
        push_proc_file_queue(mq, file, batch_id)
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
        threading.Thread(name='Ticker', target=idle_timeout_ticker, args=(mq,)), # ticker
        threading.Thread(name='ProcUrl', target=proc_url, args=(mq, driver)), # 处理 URL
    ]

    if with_progress:
        new_threads = [threading.Thread(name='Progress', target=show_progress, args=(mq,))]
        new_threads.extend(threads)
        threads = new_threads[:]

    if Path(monitor_path).is_dir(): # 监控源 为目录时 启动 目录监控 和 目录下文件排队
        if config.get('source_watch', False): # 监控目录
            send_progress_msg(mq, message=f'监控目录: {monitor_path}')
            threads.append(threading.Thread(name='PathMonitor', target=path_monitor, args=(mq, monitor_path,)))
        # 文件排队
        threads.append(threading.Thread(name='ProcFile', target=proc_file, args=(mq,)))

    def infinity_loop() -> bool:
        for cfg_key in ['source_watch', 'idle_task']:
            if config.get(cfg_key, False):
                return True
        
        return False

    [ _t.start() for _t in threads ]
    try:
        batch_id = mq.uuid(True)
        if Path(monitor_path).is_dir():
            # 处理已经存在文件
            send_files_from_path(mq, monitor_path, batch_id=batch_id)
            if not config.get('source_watch', False):         
                mq.join('file') # 等所有文件处理完成
        else:
            meta_list = [
                {'total': progress_total(data=monitor_path, meta_type=PMT.FILE), 'message': f'处理文件: {monitor_path}'},
                {'status': PMFS.Queued},
                {'status': PMFS.Processed}
            ]
            for meta in meta_list:
                send_progress_meta(
                    mq, meta_type=PMT.FILE, data=monitor_path, **meta
                )
            push_url_proc_queue(mq, monitor_path, batch_id=batch_id)
        if config.get('source_watch', False):
            send_progress_msg(mq, message=f'{monitor_path} 内容全部处理完成')
        
        if infinity_loop():
            while True: time.sleep(10)
        
        mq.join('url') # 等待 URL 处理任务完成
    except KeyboardInterrupt:
        logger.info('感谢使用，程序预计在 {} 秒内退出', quit_timeout)
        send_progress_msg(mq, message=f'感谢使用，程序预计在 {quit_timeout} 秒内退出')
    finally:
        if with_progress: mq.join('progress')
        stop_and_wait_threads(mq, threads, quit_timeout)
        driver.quit()
