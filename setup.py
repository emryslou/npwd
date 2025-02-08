from setuptools import setup, find_namespace_packages

setup(
    name='npwd', # net-page-watch-dog
    version='0.0.4',
    install_requires = [
        'importlib-metadata; python_version >= "3.10.16"',
        'loguru==0.7',
        'fake-useragent==2.0.3',
        'rich==13.9',
        'click==8.1',
        'selenium==4.24',
        'watchdog==6.0.0',
        'markdown2==2.5.3',
        'Windows-Toasts==1.3.0',
        'requests==2.32.3',
    ],
    package_dir={"": "src"},
    packages=find_namespace_packages(
        where='src',
        include=['npwd*']
    ),
    entry_points={
        'console_scripts': [
            'cli-name = npwd.cli:cli'
        ],
    },
)
