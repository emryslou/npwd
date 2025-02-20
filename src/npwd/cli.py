import time

import click
from loguru import logger
from .core import driver


@click.group()
def cli():
    pass


@cli.command()
@click.option('--expire', type=click.IntRange(3600, 864000), default=86400,
              help='过期时间: 距离创建时间过了多少, 单位 秒，')
def clear_data(expire: int = 86400):
    """ 清除之前的数据 """
    from . import core as tools
    tools.remove_expired_files(expire, tools.data_path())


@cli.command()
@click.option('--config', type=click.Path(exists=True, file_okay=True), help='配置文件路径')
@click.option('--driver-type', type=click.Choice(driver.driver_type_names()), default=driver.driver_default_type(),
              help=f'浏览器驱动类型, 默认:{driver.driver_default_type()}')
@click.option('--source', type=click.Path(exists=True), default=None, help='需要处理文件或者目录')
@click.option('--source-watch', is_flag=True, type=click.BOOL, default=False,
              help='如果 source 目录，是否需要持续监控， 默认: True')
@click.option('--headless', is_flag=True, type=click.BOOL, default=True, help='是否开启无头浏览器，默认开启: True')
@click.option('--proxy', type=click.STRING, default='',
              help='代理地址, 格式: {ip or host}:{port}, 例如： 127.0.0.1:8080, proxy.host.com:9900')
@click.option('--timeout', type=click.IntRange(1, 3600), default=60, help='超时时间, 单位: 秒, 默认: 60')
@click.option('--tab-count', type=click.IntRange(1, 15), default=2, help='默认打开 标签页个数, 默认: 2')
@click.option('--scroll-window-size', is_flag=True, type=click.BOOL, default=False, help='是否滚动窗口, 默认: False')
@click.option('--with-progress', is_flag=True, type=click.BOOL, default=False, help='是否显示进度, 默认: False')
@click.option('--idle-task', is_flag=True, type=click.BOOL, default=False,
              help='是否启动空闲超时任务, 仅在 source 为目录时有效')
@click.option('--idle-timeout', type=click.IntRange(10, 86400), default=600, help='队列空闲超过多少秒后启动，默认: 600')
@click.option('--log-level', type=click.Choice(['TRACE', 'DEBUG', 'INFO', 'SUCCESS', 'WARNING', 'ERROR', 'CRITICAL'],
                                               case_sensitive=False), default='INFO', help='日志显示级别, 默认: INFO')
def run(**kwargs):
    """ 爬取指定目录或文件的 url
    """
    if 'source' not in kwargs and 'config' not in kwargs:
        raise click.UsageError('--source 或者 --config 必须至少提供一个')

    from .core import config, load_handlers, log_path, data_path, bin_path, log_path, root_path, Path
    import sys
    from . import app

    config.init(**kwargs)

    if not Path(config.get('runtime_path')).exists():
        if not click.confirm('是否需要初始化环境运行环境?', default=True):
            click.echo('好的，感谢您的使用，拜拜')
            return
        logger.info('初始化运行环境...')
        Path(config.get('runtime_path')).mkdir(parents=True)
        for path_func in [data_path, bin_path, log_path]:
            path: Path = path_func()
            if path.exists():
                continue
            path.mkdir(parents=True)

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
@click.option('--path', type=click.Path(file_okay=True), help='存储路径', required=True)
def dump_config(path: str):
    """导出配置到指定文件"""
    from .core import config
    from pathlib import Path
    save_path = Path(path)
    config.dump(save_path, save_path.name.split('.')[-1])


@cli.command()
@click.option('--headless', is_flag=True, type=click.BOOL, default=False, help='是否开启无头浏览器，默认关闭: False')
def start_browser(**kwargs):
    from .core import config, driver as driver_lib
    config.init(**kwargs)
    try:
        driver_type = driver_lib.DriverType.__dict__['_member_map_'][driver_lib.driver_default_type()]
        browser = driver_lib.init_driver(driver_type)
        browser.get('about:blank')
        while True:
            try:
                browser.title
                time.sleep(5)
            except:  # browser 出错，则直接退出
                break
    except KeyboardInterrupt:
        print('Ctrl + C')
    finally:
        browser.quit()


@cli.command()
def dev():
    pass


if __name__ == '__main__':
    cli()
