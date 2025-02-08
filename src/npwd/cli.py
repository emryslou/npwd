import http.client
import click
from loguru import logger

@click.group()
def cli():
    pass

@cli.command()
@click.option('--expire', type=click.IntRange(3600, 864000), default=86400, help='过期时间: 距离创建时间过了多少, 单位 秒，')
def clear_data(expire: int = 86400):
    """ 清除之前的数据 """
    from . import utils as tools
    tools.remove_expired_files(expire, tools.data_path())



@cli.command()
@click.option('--source', type=click.Path(exists=True), default=None, help='需要处理文件或者目录', required=True)
@click.option('--source-watch', is_flag=True, type=click.BOOL, default=False, help='如果 source 目录，是否需要持续监控， 默认: True')
@click.option('--headless', is_flag=True, type=click.BOOL, default=True, help='是否开启无头浏览器，默认开启: True')
@click.option('--proxy', type=click.STRING, default='', help='代理地址, 格式: {ip or host}:{port}, 例如： 127.0.0.1:8080, proxy.host.com:9900')
@click.option('--timeout', type=click.IntRange(1, 3600), default=60, help='超时时间, 单位: 秒, 默认: 60')
@click.option('--tab-count', type=click.IntRange(1, 15), default=2, help='默认打开 标签页个数, 默认: 2')
@click.option('--scroll-window-size', is_flag=True, type=click.BOOL, default=False, help='是否滚动窗口, 默认: False')
@click.option('--with-progress', is_flag=True, type=click.BOOL, default=False, help='是否显示进度, 默认: False')
@click.option('--idle-task', is_flag=True, type=click.BOOL, default=False, help='是否启动空闲超时任务, 仅在 source 为目录时有效')
@click.option('--idle-timeout', type=click.IntRange(10, 86400), default=600, help='队列空闲超过多少秒后启动，默认: 600')
@click.option('--log-level', type=click.Choice(['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False), default='INFO', help='日志显示级别, 默认: INFO')
def run(**kwargs):
    """ 爬取指定目录或文件的 url
    """
    from .core import config
    from .utils import load_handlers, log_path
    import sys
    from . import app
        
    config.init(**kwargs)
    
    logger.remove()
    log_level = str(config.get('log_level', 'INFO')).upper()
    with_progress = config.get('with_progress', False)
    logger.add(str(log_path().joinpath('npwd.log')) if with_progress else sys.stderr, level=log_level)
    logger.info('Config: {}', config.all())

    load_handlers(config.get('url_handlers', []))
    app.start()

@cli.command()
def version():
    """ 版本信息"""
    from . import app
    print('版本号 app: ', app.__version__)


@cli.command()
@click.option('--runtime-path', type=click.Path(exists=True), default=None, help='需要初始化的路径, 默认: None')
def runtime_init(runtime_path: str | None = None):
    from pathlib import Path
    from .utils import data_path, bin_path, log_path, platform

    def bin_path_init():
        import requests, json
        from urllib3.util import parse_url
        chrome_driver_src = 'https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json'
        r = requests.get(url=chrome_driver_src)
        if r.status_code != 200:
            return
        all_dl_info:dict = json.loads(r.content)
        run_pf = platform()
        if run_pf.lower().startswith('win'):
            downloads_info = []
            for dl in all_dl_info['versions']:
                if not dl['version'].startswith('132'):
                    continue
                downloads_info.extend([
                    {'version': dl['version'], 'url': dl_url['url']} for dl_url in dl['downloads']['chrome']
                    if dl_url['platform'] == 'win64'
                ])
        else:
            downloads_info = []

        r = requests.get(url=downloads_info[-1]['url'], stream=True)
        if r.status_code == 200:
            print('dl .... ')
            with open(bin_path().joinpath('dl.zip'), 'wb') as f:
                f.write(r.content)
            print('dl done')

    for path_func in [data_path, bin_path, log_path]:
        path: Path = path_func()
        if path.exists():
            continue
        path.mkdir(parents=True)
    
    bin_path_init()


if __name__ == '__main__':
    cli()
