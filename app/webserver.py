import base64
import logging
import os
import asyncio
import signal
import ipaddress
from configparser import ConfigParser

import click
import jinja2
import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet
from concurrent.futures import ThreadPoolExecutor

from . import views


def config_load(config_file):
    config = ConfigParser(allow_no_value=True)
    config.read(config_file)
    return config


def config_logging(config, log_level=None):
    log_level = log_level or config.get('log', 'level', fallback='info')
    log_format = config.get('log', 'format', fallback='%(asctime)s %(levelname)-8s %(message)s')
    level = getattr(logging, log_level.upper())
    logging.basicConfig(level=level, format=log_format)


def root_package_name():
    return __name__.split('.')[0]


def root_package_path(relative_path=None):
    root_module = __import__(root_package_name())
    path = os.path.dirname(os.path.abspath(root_module.__file__))
    if relative_path is not None:
        path = os.path.join(path, relative_path)
    return path


class WebServer:
    def __init__(self, config, loop=None):
        self._loop = loop
        self._srv = None
        self._handler = None
        self._app = None
        self._cfg = config

    async def start(self):
        # Fernet key must be 32 bytes.
        cookie_secret = self._cfg.get('http', 'cookie_secret', fallback=None)
        if cookie_secret is None:
            cookie_secret = base64.urlsafe_b64decode(Fernet.generate_key())
        middlewares = [
            session_middleware(EncryptedCookieStorage(cookie_secret)),
        ]
        self._app = web.Application(middlewares=middlewares)
        self._app.data_dir =  self._cfg.get('http', 'data', fallback='./data')
        default_creds = os.path.join(self._app.data_dir, 'credentials')
        self._app.credentials_file = self._cfg.get('http', 'data', fallback=default_creds)
        self._app.ioloop = self._loop
        self._app.som_url_format = self._cfg.get('http', 'som-url', fallback=None)
        self._app.meta_data_cache = {}

        net_whitelist = self._cfg.get('http', 'whitelist', fallback='127.0.0.1/32')
        if net_whitelist is not None:
            self._app.net_whitelist = [ipaddress.ip_network(net) for net in net_whitelist.split()]

        self._executor = ThreadPoolExecutor(4)
        self._loop.set_default_executor(self._executor)

        def jinja_url_helper(route_name, *args, **kwargs):
            return self._app.router[route_name].url(*args, **kwargs)

        jinja_env = aiohttp_jinja2.setup(
            self._app,
            loader=jinja2.FileSystemLoader(root_package_path('templates')))
        jinja_env.globals['url'] = jinja_url_helper

        for handler, args, kwargs in views.handlers:
            path, = args
            methods = kwargs.get('methods', ['GET'])
            name = kwargs.get('name')
            for method in methods:
                self._app.router.add_route(method, path, handler, name=name)

        self._app.router.add_static('/images', self._app.data_dir)
        self._app.router.add_static('/', root_package_path('web-static'), name='static')

        host, port = self._cfg.get('http', 'bind', fallback='127.0.0.1:8000').split(':')
        self._handler = self._app.make_handler()
        self._srv = await self._loop.create_server(self._handler, host, int(port))

    async def stop(self):
        await self._handler.finish_connections(1.0)
        self._srv.close()
        await self._srv.wait_closed()
        await self._app.finish()


@click.command()
@click.option('-c', '--config', 'config_file', required=True, type=click.Path(exists=True, dir_okay=False))
@click.option('-l', '--log-level', 'log_level')
def cli(config_file, log_level):
    config = config_load(config_file)
    config_logging(config, log_level)

    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, loop.stop)
    except NotImplementedError:
        # signals are not available on Windows
        pass

    webserver = WebServer(config, loop=loop)
    loop.run_until_complete(webserver.start())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(webserver.stop())
        # дожидаемся завершения всех оставшихся задач и выходим.
        pending = asyncio.Task.all_tasks()
        loop.run_until_complete(asyncio.gather(*pending))
        loop.close()
